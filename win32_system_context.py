import ctypes
from ctypes import wintypes
import re
from typing import Iterator, List, Optional, Tuple


TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_IS_64BIT_HOST = ctypes.sizeof(ctypes.c_void_p) == 8


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    """Cấu trúc MEMORY_BASIC_INFORMATION chuẩn cho cả Python 32-bit (28B) và 64-bit (48B)."""

    if _IS_64BIT_HOST:
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", wintypes.DWORD),
            ("PartitionId", wintypes.WORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", wintypes.DWORD),
            ("Protect", wintypes.DWORD),
            ("Type", wintypes.DWORD),
        ]
    else:
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", wintypes.DWORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", wintypes.DWORD),
            ("Protect", wintypes.DWORD),
            ("Type", wintypes.DWORD),
        ]


class SYSTEM_INFO(ctypes.Structure):
    """Cấu trúc SYSTEM_INFO dùng để xác định giới hạn không gian địa chỉ ảo."""

    _fields_ = [
        ("wProcessorArchitecture", wintypes.WORD),
        ("wReserved", wintypes.WORD),
        ("dwPageSize", wintypes.DWORD),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_void_p),
        ("dwNumberOfProcessors", wintypes.DWORD),
        ("dwProcessorType", wintypes.DWORD),
        ("dwAllocationGranularity", wintypes.DWORD),
        ("wProcessorLevel", wintypes.WORD),
        ("wProcessorRevision", wintypes.WORD),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    """Cấu trúc PROCESSENTRY32W phục vụ liệt kê và tìm PID theo tên tiến trình."""

    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class Win32SystemContext:
    """Khung nền tảng quản lý tiến trình, phân vùng ảo, AOB Scanner và Pointer Resolver."""

    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    PROCESS_QUERY_INFORMATION = 0x0400

    MEM_COMMIT = 0x1000

    PAGE_NOACCESS = 0x01
    PAGE_GUARD = 0x100

    PAGE_EXECUTE_READ = 0x20
    PAGE_EXECUTE_READWRITE = 0x40
    PAGE_EXECUTE_WRITECOPY = 0x80
    READABLE_EXECUTABLE_FLAGS = (
        PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY
    )

    PAGE_READONLY = 0x02
    PAGE_READWRITE = 0x04
    PAGE_WRITECOPY = 0x08
    READABLE_DATA_FLAGS = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY

    SCAN_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB mỗi khối quét để tránh cấp phát quá lớn

    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._initialize_signatures()

    def _initialize_signatures(self) -> None:
        self.kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self.kernel32.OpenProcess.restype = wintypes.HANDLE

        self.kernel32.ReadProcessMemory.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.kernel32.ReadProcessMemory.restype = wintypes.BOOL

        self.kernel32.WriteProcessMemory.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.kernel32.WriteProcessMemory.restype = wintypes.BOOL

        self.kernel32.VirtualQueryEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.POINTER(MEMORY_BASIC_INFORMATION),
            ctypes.c_size_t,
        ]
        self.kernel32.VirtualQueryEx.restype = ctypes.c_size_t

        self.kernel32.GetSystemInfo.argtypes = [ctypes.POINTER(SYSTEM_INFO)]
        self.kernel32.GetSystemInfo.restype = None

        self.kernel32.CreateToolhelp32Snapshot.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self.kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

        self.kernel32.Process32FirstW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESSENTRY32W),
        ]
        self.kernel32.Process32FirstW.restype = wintypes.BOOL

        self.kernel32.Process32NextW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESSENTRY32W),
        ]
        self.kernel32.Process32NextW.restype = wintypes.BOOL

        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    def find_process_id(self, process_name: str) -> Optional[int]:
        """Tìm PID của tiến trình theo tên tệp thực thi (không phân biệt hoa thường)."""
        target_lower = process_name.strip().lower()
        if not target_lower:
            return None

        h_snap = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not h_snap or h_snap == INVALID_HANDLE_VALUE:
            err_code = ctypes.get_last_error()
            raise ctypes.WinError(err_code, "CreateToolhelp32Snapshot thất bại.")

        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not self.kernel32.Process32FirstW(h_snap, ctypes.byref(entry)):
                return None

            while True:
                if entry.szExeFile.lower() == target_lower:
                    return int(entry.th32ProcessID)
                if not self.kernel32.Process32NextW(h_snap, ctypes.byref(entry)):
                    break
        finally:
            self.kernel32.CloseHandle(h_snap)

        return None

    def _get_address_bounds(self) -> Tuple[int, int]:
        sys_info = SYSTEM_INFO()
        self.kernel32.GetSystemInfo(ctypes.byref(sys_info))
        min_addr = sys_info.lpMinimumApplicationAddress or 0x10000
        max_addr = sys_info.lpMaximumApplicationAddress or (
            0x7FFFFFFEFFFF if _IS_64BIT_HOST else 0x7FFEFFFF
        )
        return int(min_addr), int(max_addr)

    @classmethod
    def _is_scannable_region(
        cls,
        mbi: MEMORY_BASIC_INFORMATION,
        require_executable: bool = True,
    ) -> bool:
        if mbi.State != cls.MEM_COMMIT or mbi.RegionSize == 0:
            return False

        protect = mbi.Protect
        if protect & (cls.PAGE_GUARD | cls.PAGE_NOACCESS):
            return False

        allowed_mask = (
            cls.READABLE_EXECUTABLE_FLAGS
            if require_executable
            else (cls.READABLE_EXECUTABLE_FLAGS | cls.READABLE_DATA_FLAGS)
        )
        return bool(protect & allowed_mask)

    @staticmethod
    def compile_aob_pattern(pattern: str) -> re.Pattern[bytes]:
        """
        Biên dịch chuỗi mẫu AOB (VD: '48 8B 05 ?? ?? ?? ??' hoặc '48 8B ? ?')
        thành biểu thức chính quy nhị phân hỗ trợ wildcard.
        """
        tokens = pattern.strip().split()
        if not tokens:
            raise ValueError("Mẫu AOB không được để trống.")

        regex_parts: List[bytes] = []
        for token in tokens:
            if token in ("?", "??", "**"):
                regex_parts.append(b".")
            else:
                if len(token) != 2:
                    raise ValueError(f"Token byte không hợp lệ: '{token}'")
                byte_val = int(token, 16)
                regex_parts.append(re.escape(bytes([byte_val])))

        return re.compile(b"".join(regex_parts), flags=re.DOTALL)

    def iter_memory_regions(
        self,
        h_process: int,
        start_address: Optional[int] = None,
        end_address: Optional[int] = None,
        require_executable: bool = True,
    ) -> Iterator[Tuple[int, int]]:
        """
        Duyệt các phân vùng bộ nhớ ảo hợp lệ của tiến trình qua VirtualQueryEx.
        Trả về tuple (base_address, region_size).
        """
        min_addr, max_addr = self._get_address_bounds()
        current_addr = max(start_address or min_addr, min_addr)
        limit_addr = min(end_address or max_addr, max_addr)

        mbi = MEMORY_BASIC_INFORMATION()
        mbi_size = ctypes.sizeof(mbi)

        while current_addr < limit_addr:
            queried = self.kernel32.VirtualQueryEx(
                h_process,
                ctypes.c_void_p(current_addr),
                ctypes.byref(mbi),
                mbi_size,
            )
            if queried == 0:
                break

            base_addr = int(mbi.BaseAddress or current_addr)
            region_size = int(mbi.RegionSize)
            if region_size <= 0:
                break

            if self._is_scannable_region(mbi, require_executable=require_executable):
                scan_start = max(base_addr, current_addr)
                scan_end = min(base_addr + region_size, limit_addr)
                if scan_end > scan_start:
                    yield scan_start, scan_end - scan_start

            next_addr = base_addr + region_size
            if next_addr <= current_addr:
                break
            current_addr = next_addr

    def scan_pattern(
        self,
        process_id: int,
        pattern: str,
        *,
        require_executable: bool = True,
        first_match_only: bool = False,
        start_address: Optional[int] = None,
        end_address: Optional[int] = None,
    ) -> List[int]:
        """
        Quét mẫu byte AOB có wildcard trên toàn bộ vùng nhớ hợp lệ của tiến trình
        theo từng khối an toàn (tránh tràn bộ nhớ với các phân vùng lớn).
        """
        tokens = pattern.strip().split()
        compiled_regex = self.compile_aob_pattern(pattern)
        overlap = max(len(tokens) - 1, 0)
        access_flags = self.PROCESS_QUERY_INFORMATION | self.PROCESS_VM_READ

        h_process = self.kernel32.OpenProcess(access_flags, False, process_id)
        if not h_process:
            err_code = ctypes.get_last_error()
            raise ctypes.WinError(err_code, f"OpenProcess thất bại (PID={process_id})")

        matches: List[int] = []
        seen: set[int] = set()
        try:
            for region_base, region_size in self.iter_memory_regions(
                h_process,
                start_address=start_address,
                end_address=end_address,
                require_executable=require_executable,
            ):
                offset = 0
                while offset < region_size:
                    read_len = min(self.SCAN_CHUNK_SIZE, region_size - offset)
                    chunk_addr = region_base + offset
                    buffer = (ctypes.c_char * read_len)()
                    bytes_read = ctypes.c_size_t(0)

                    ok = self.kernel32.ReadProcessMemory(
                        h_process,
                        ctypes.c_void_p(chunk_addr),
                        buffer,
                        read_len,
                        ctypes.byref(bytes_read),
                    )
                    if ok and bytes_read.value > 0:
                        chunk_bytes = memoryview(buffer)[: bytes_read.value].tobytes()
                        for match in compiled_regex.finditer(chunk_bytes):
                            hit_addr = chunk_addr + match.start()
                            if hit_addr not in seen:
                                seen.add(hit_addr)
                                matches.append(hit_addr)
                                if first_match_only:
                                    return matches

                    if offset + read_len >= region_size:
                        break
                    step = max(read_len - overlap, 1)
                    offset += step

            return matches
        finally:
            self.kernel32.CloseHandle(h_process)

    @staticmethod
    def resolve_rip_relative(
        instruction_address: int,
        displacement_offset: int,
        instruction_length: int,
        instruction_bytes: bytes,
    ) -> int:
        """
        Tính địa chỉ đích tuyệt đối từ lệnh tham chiếu RIP-relative trên x86_64
        (VD: '48 8B 05 ?? ?? ?? ??' có displacement_offset=3, instruction_length=7).
        """
        disp_bytes = instruction_bytes[displacement_offset : displacement_offset + 4]
        if len(disp_bytes) != 4:
            raise ValueError("Không đủ 4 byte displacement để giải mã RIP-relative.")
        signed_disp = int.from_bytes(disp_bytes, byteorder="little", signed=True)
        return instruction_address + instruction_length + signed_disp

    def _read_memory_raw(
        self,
        h_process: int,
        address: int,
        size: int,
    ) -> bytes:
        """Hàm nội bộ đọc vùng nhớ khi đã có sẵn `h_process`."""
        buffer = (ctypes.c_char * size)()
        bytes_read = ctypes.c_size_t(0)
        ok = self.kernel32.ReadProcessMemory(
            h_process,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read),
        )
        if not ok or bytes_read.value != size:
            err_code = ctypes.get_last_error()
            raise ctypes.WinError(
                err_code,
                f"ReadProcessMemory thất bại tại 0x{address:X} (yêu cầu {size} bytes)",
            )
        return memoryview(buffer)[: bytes_read.value].tobytes()

    def read_bytes(
        self,
        process_id: int,
        base_address: int,
        size: int,
    ) -> bytes:
        """Đọc vùng nhớ kích thước `size` từ `base_address` của tiến trình."""
        if size <= 0:
            return b""

        access_flags = self.PROCESS_QUERY_INFORMATION | self.PROCESS_VM_READ
        h_process = self.kernel32.OpenProcess(access_flags, False, process_id)
        if not h_process:
            err_code = ctypes.get_last_error()
            raise ctypes.WinError(err_code, f"OpenProcess thất bại (PID={process_id})")

        try:
            return self._read_memory_raw(h_process, base_address, size)
        finally:
            self.kernel32.CloseHandle(h_process)

    def read_pointer_chain(
        self,
        process_id: int,
        base_address: int,
        offsets: List[int],
        pointer_size: int = 8,
    ) -> int:
        """
        Duyệt chuỗi con trỏ đa cấp chuẩn:
        [...[base_address] + offsets[0]] + offsets[1] ... + offsets[-1] -> target_address.
        - `pointer_size`: 8 cho tiến trình 64-bit, 4 cho tiến trình 32-bit (x86).
        """
        if pointer_size not in (4, 8):
            raise ValueError("pointer_size chỉ hỗ trợ 4 (32-bit) hoặc 8 (64-bit).")

        access_flags = self.PROCESS_QUERY_INFORMATION | self.PROCESS_VM_READ
        h_process = self.kernel32.OpenProcess(access_flags, False, process_id)
        if not h_process:
            err_code = ctypes.get_last_error()
            raise ctypes.WinError(err_code, f"OpenProcess thất bại (PID={process_id})")

        try:
            ptr_bytes = self._read_memory_raw(h_process, base_address, pointer_size)
            current_addr = int.from_bytes(ptr_bytes, byteorder="little", signed=False)
            if current_addr == 0:
                raise ValueError(f"Con trỏ gốc bị null (0) tại 0x{base_address:X}")

            if not offsets:
                return current_addr

            for level, offset in enumerate(offsets[:-1]):
                next_ptr_addr = current_addr + offset
                ptr_bytes = self._read_memory_raw(h_process, next_ptr_addr, pointer_size)
                current_addr = int.from_bytes(ptr_bytes, byteorder="little", signed=False)
                if current_addr == 0:
                    raise ValueError(
                        f"Con trỏ bị null (0) tại cấp {level + 1} "
                        f"(Địa chỉ: 0x{next_ptr_addr:X}, Offset: 0x{offset:X})"
                    )

            return current_addr + offsets[-1]
        finally:
            self.kernel32.CloseHandle(h_process)

    def write_bytes_sequential(
        self,
        process_id: int,
        base_address: int,
        data: bytes | bytearray | memoryview,
        chunk_size: int = 0,
    ) -> int:
        """
        Ghi tuần tự mảng byte `data` vào `base_address` của tiến trình `process_id`.
        Nếu `chunk_size > 0`, dữ liệu được chia nhỏ và ghi nối tiếp từng khối.
        Trả về tổng số byte đã ghi thành công.
        """
        raw_bytes = bytes(data)
        total_len = len(raw_bytes)
        if total_len == 0:
            return 0

        desired_access = self.PROCESS_VM_OPERATION | self.PROCESS_VM_WRITE
        h_process = self.kernel32.OpenProcess(desired_access, False, process_id)
        if not h_process:
            err_code = ctypes.get_last_error()
            raise ctypes.WinError(err_code, f"OpenProcess thất bại (PID={process_id})")

        try:
            step = chunk_size if chunk_size > 0 else total_len
            total_written = 0
            src_buffer = (ctypes.c_char * total_len).from_buffer_copy(raw_bytes)
            base_src_ptr = ctypes.addressof(src_buffer)

            while total_written < total_len:
                current_size = min(step, total_len - total_written)
                target_addr = ctypes.c_void_p(base_address + total_written)
                current_src_ptr = ctypes.c_void_p(base_src_ptr + total_written)
                bytes_written = ctypes.c_size_t(0)

                ok = self.kernel32.WriteProcessMemory(
                    h_process,
                    target_addr,
                    current_src_ptr,
                    current_size,
                    ctypes.byref(bytes_written),
                )
                if not ok or bytes_written.value == 0:
                    err_code = ctypes.get_last_error()
                    raise ctypes.WinError(
                        err_code,
                        f"WriteProcessMemory thất bại tại 0x{base_address + total_written:X}",
                    )

                total_written += bytes_written.value

            return total_written
        finally:
            self.kernel32.CloseHandle(h_process)
