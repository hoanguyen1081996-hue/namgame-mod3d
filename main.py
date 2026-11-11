import argparse
from dataclasses import dataclass
import logging
from pathlib import Path
import sqlite3
import sys
from typing import List, Optional, Sequence, Tuple

from win32_system_context import Win32SystemContext


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ProcessResourceManager")


def get_runtime_dirs() -> Tuple[Path, Path]:
    """
    Xác định cặp thư mục thực thi chuẩn cho cả môi trường Python thuần và bản đóng gói PyInstaller:
    - `app_dir`: Thư mục chứa tệp `.exe` (hoặc `main.py`) — dùng cho cấu hình người dùng & dữ liệu ngoài.
    - `bundle_dir`: Thư mục giải nén nội bộ `_MEIPASS` khi đóng gói `--onefile` (hoặc `app_dir` khi chạy script).
    """
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", app_dir)).resolve()
    else:
        app_dir = Path(__file__).resolve().parent
        bundle_dir = app_dir
    return app_dir, bundle_dir


@dataclass(frozen=True)
class CatalogItem:
    """Mô hình dữ liệu vật phẩm truy vấn từ bảng `equip` trong inject_catalog.db."""

    code: str
    mesh: str
    name: str
    slot: str
    item_type: int
    icon: str
    group: str

    def to_payload_bytes(
        self,
        field: str = "mesh",
        encoding: str = "ascii",
        null_terminated: bool = True,
        fixed_length: Optional[int] = None,
    ) -> bytes:
        raw_text = getattr(self, field)
        payload = raw_text.encode(encoding)
        if null_terminated:
            payload += b"\x00"
        if fixed_length is not None:
            if len(payload) > fixed_length:
                raise ValueError(
                    f"Kích thước payload ({len(payload)}B) vượt giới hạn cố định ({fixed_length}B)."
                )
            payload = payload.ljust(fixed_length, b"\x00")
        return payload


class CatalogRepository:
    """Quản lý truy vấn cơ sở dữ liệu SQLite cục bộ (`inject_catalog.db`)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = self._resolve_db_path(db_path)

    @staticmethod
    def _resolve_db_path(candidate: Path) -> Path:
        if candidate.is_file():
            return candidate.resolve()

        app_dir, bundle_dir = get_runtime_dirs()
        fallbacks = [
            app_dir / "data" / "inject_catalog.db",
            bundle_dir / "data" / "inject_catalog.db",
            app_dir / "namgame_tool" / "data" / "inject_catalog.db",
            app_dir / "EquipInjectTest_me_pro115_kem_data" / "data" / "inject_catalog.db",
        ]
        for path in fallbacks:
            if path.is_file():
                return path.resolve()
        raise FileNotFoundError(f"Không tìm thấy cơ sở dữ liệu catalog tại: {candidate}")

    def _connect_ro(self) -> sqlite3.Connection:
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def get_item_by_code(self, code: str) -> CatalogItem:
        query = """
            SELECT code, mesh, COALESCE(name, ''), COALESCE(slot, ''), COALESCE(type, 0),
                   COALESCE(icon, ''), COALESCE(grp, 'main')
            FROM equip
            WHERE UPPER(code) = UPPER(?)
            LIMIT 1
        """
        with self._connect_ro() as conn:
            row = conn.execute(query, (code.strip(),)).fetchone()

        if row is None:
            raise LookupError(f"Mã vật phẩm '{code}' không tồn tại trong {self.db_path.name}.")

        return CatalogItem(
            code=row[0],
            mesh=row[1],
            name=row[2],
            slot=row[3],
            item_type=int(row[4]),
            icon=row[5],
            group=row[6],
        )

    def search_items(
        self,
        keyword: str = "",
        slot: Optional[str] = None,
        limit: int = 20,
    ) -> List[CatalogItem]:
        clauses: List[str] = []
        params: List[object] = []

        if keyword.strip():
            clauses.append(
                "(UPPER(code) LIKE UPPER(?) OR UPPER(mesh) LIKE UPPER(?) OR name LIKE ?)"
            )
            kw = f"%{keyword.strip()}%"
            params.extend([kw, kw, kw])

        if slot is not None:
            clauses.append("UPPER(COALESCE(slot, '')) = UPPER(?)")
            params.append(slot.strip())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT code, mesh, COALESCE(name, ''), COALESCE(slot, ''), COALESCE(type, 0),
                   COALESCE(icon, ''), COALESCE(grp, 'main')
            FROM equip
            {where_sql}
            ORDER BY grp, type, code
            LIMIT ?
        """
        params.append(limit)

        with self._connect_ro() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            CatalogItem(
                code=r[0],
                mesh=r[1],
                name=r[2],
                slot=r[3],
                item_type=int(r[4]),
                icon=r[5],
                group=r[6],
            )
            for r in rows
        ]


class ProcessCatalogSynchronizer:
    """Điều phối luồng truy vấn SQLite Catalog -> AOB Scan -> Pointer Chain -> WriteProcessMemory."""

    def __init__(self, ctx: Win32SystemContext, repo: CatalogRepository) -> None:
        self.ctx = ctx
        self.repo = repo

    def find_pid_by_name(self, process_name: str) -> int:
        pid = self.ctx.find_process_id(process_name)
        if pid is None:
            raise ProcessLookupError(
                f"Không tìm thấy tiến trình '{process_name}' đang chạy."
            )
        return pid

    def execute_pipeline(
        self,
        *,
        item_code: str,
        aob_pattern: str,
        pointer_offsets: Sequence[int],
        process_id: Optional[int] = None,
        process_name: Optional[str] = None,
        pointer_size: int = 4,
        pattern_offset: int = 0,
        rip_relative: Optional[Tuple[int, int]] = None,
        require_executable: bool = True,
        payload_field: str = "mesh",
        chunk_size: int = 0,
    ) -> int:
        # Bước 1: Truy vấn dữ liệu vật phẩm từ SQLite Catalog
        logger.info("Bước 1/4: Kết nối SQLite Catalog tại '%s'", self.repo.db_path)
        item = self.repo.get_item_by_code(item_code)
        payload = item.to_payload_bytes(field=payload_field, null_terminated=True)
        logger.info(
            "Đã nạp vật phẩm: Code=%s | Mesh=%s | Name='%s' | Slot=%s (Type=%d) | Payload=%s (%d bytes)",
            item.code,
            item.mesh,
            item.name,
            item.slot,
            item.item_type,
            payload.hex(" ").upper(),
            len(payload),
        )

        # Xác định PID mục tiêu
        pid = (
            process_id
            if process_id is not None
            else self.find_pid_by_name(process_name or "")
        )
        logger.info("Tiến trình mục tiêu đã xác nhận: PID=%d", pid)

        # Bước 2: Quét mẫu byte AOB tìm địa chỉ cơ sở động
        logger.info(
            "Bước 2/4: Quét mẫu AOB '%s' (executable=%s)...",
            aob_pattern,
            require_executable,
        )
        matches = self.ctx.scan_pattern(
            pid,
            aob_pattern,
            require_executable=require_executable,
            first_match_only=True,
        )
        if not matches:
            raise LookupError(
                f"Không tìm thấy mẫu AOB '{aob_pattern}' trong tiến trình PID={pid}."
            )

        matched_addr = matches[0]
        if rip_relative is not None:
            disp_offset, instr_len = rip_relative
            instr_bytes = self.ctx.read_bytes(pid, matched_addr, instr_len)
            dynamic_base = self.ctx.resolve_rip_relative(
                matched_addr, disp_offset, instr_len, instr_bytes
            )
            logger.info(
                "Tìm thấy mẫu AOB tại 0x%X -> Địa chỉ RIP-relative giải mã được: 0x%X",
                matched_addr,
                dynamic_base,
            )
        else:
            dynamic_base = matched_addr + pattern_offset
            logger.info(
                "Tìm thấy mẫu AOB tại 0x%X -> Địa chỉ cơ sở động (sau pattern_offset=%+d): 0x%X",
                matched_addr,
                pattern_offset,
                dynamic_base,
            )

        # Bước 3: Giải mã chuỗi con trỏ đa cấp để xác định địa chỉ vùng nhớ đích
        offsets_list = list(pointer_offsets)
        logger.info(
            "Bước 3/4: Giải mã chuỗi con trỏ từ 0x%X với offsets=%s (pointer_size=%dB)...",
            dynamic_base,
            [f"0x{o:X}" for o in offsets_list],
            pointer_size,
        )
        target_address = self.ctx.read_pointer_chain(
            process_id=pid,
            base_address=dynamic_base,
            offsets=offsets_list,
            pointer_size=pointer_size,
        )
        logger.info("Đã phân giải địa chỉ vùng nhớ đích: 0x%X", target_address)

        # Bước 4: Ghi tuần tự dữ liệu payload vào vùng nhớ đích
        logger.info(
            "Bước 4/4: Ghi tuần tự %d bytes vào địa chỉ 0x%X (chunk_size=%d)...",
            len(payload),
            target_address,
            chunk_size,
        )
        written = self.ctx.write_bytes_sequential(
            process_id=pid,
            base_address=target_address,
            data=payload,
            chunk_size=chunk_size,
        )
        logger.info(
            "Hoàn tất! Đã ghi thành công %d/%d bytes vào PID=%d tại 0x%X.",
            written,
            len(payload),
            pid,
            target_address,
        )
        return written


def _parse_hex_int(value: str) -> int:
    return int(value.strip(), 0)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trình điều phối SQLite Catalog, AOB Pattern Scanner & Pointer Chain Writer."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/inject_catalog.db"),
        help="Đường dẫn tới tệp SQLite inject_catalog.db",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Liệt kê nhanh danh sách vật phẩm từ catalog rồi thoát",
    )
    parser.add_argument(
        "--search",
        type=str,
        default="",
        help="Từ khóa tìm kiếm mã code, mesh hoặc tên vật phẩm khi dùng --list",
    )
    parser.add_argument("--pid", type=int, help="PID của tiến trình mục tiêu")
    parser.add_argument(
        "--process-name", type=str, help="Tên tệp thực thi mục tiêu (VD: MSango.bin)"
    )
    parser.add_argument(
        "--code", type=str, help="Mã vật phẩm trong bảng equip (VD: H566, AY32)"
    )
    parser.add_argument(
        "--pattern", type=str, help="Chuỗi mẫu AOB (VD: '8B 0D ?? ?? ?? ??')"
    )
    parser.add_argument(
        "--pattern-offset",
        type=_parse_hex_int,
        default=0,
        help="Độ lệch cộng thêm vào địa chỉ khớp AOB (hỗ trợ số nguyên hoặc 0xHEX)",
    )
    parser.add_argument(
        "--offsets",
        type=_parse_hex_int,
        nargs="*",
        default=[],
        help="Danh sách các bậc offset con trỏ (VD: 0x10 0x24 0x08)",
    )
    parser.add_argument(
        "--pointer-size",
        type=int,
        choices=(4, 8),
        default=4,
        help="Kích thước con trỏ của tiến trình đích: 4 (32-bit) hoặc 8 (64-bit)",
    )
    parser.add_argument(
        "--scan-data",
        action="store_true",
        help="Quét cả các phân vùng dữ liệu đọc được thay vì chỉ vùng thực thi",
    )
    parser.add_argument(
        "--field",
        choices=("mesh", "code"),
        default="mesh",
        help="Trường dữ liệu của CatalogItem cần tuần tự hóa thành mảng byte để ghi",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        help="Kích thước mỗi khối ghi tuần tự (0 = ghi toàn bộ trong một lượt)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        repo = CatalogRepository(args.db)

        if args.list:
            items = repo.search_items(keyword=args.search, limit=25)
            logger.info("Tìm thấy %d bản ghi từ '%s':", len(items), repo.db_path)
            for item in items:
                print(
                    f"  [{item.group:<4}] Code={item.code:<6} | Mesh={item.mesh:<6} | "
                    f"Slot={item.slot:<10} (Type={item.item_type:<2}) | {item.name}"
                )
            return 0

        if not args.code or not args.pattern or (args.pid is None and not args.process_name):
            logger.error(
                "Thiếu tham số bắt buộc: cần truyền (--pid hoặc --process-name), --code và --pattern "
                "(hoặc chạy với --list để tra cứu catalog)."
            )
            return 2

        ctx = Win32SystemContext()
        sync = ProcessCatalogSynchronizer(ctx=ctx, repo=repo)
        sync.execute_pipeline(
            item_code=args.code,
            aob_pattern=args.pattern,
            pointer_offsets=args.offsets,
            process_id=args.pid,
            process_name=args.process_name,
            pointer_size=args.pointer_size,
            pattern_offset=args.pattern_offset,
            require_executable=not args.scan_data,
            payload_field=args.field,
            chunk_size=args.chunk_size,
        )
        return 0

    except (FileNotFoundError, LookupError, ProcessLookupError, ValueError) as exc:
        logger.error("Lỗi dữ liệu / định vị: %s", exc)
        return 1
    except OSError as exc:
        logger.error(
            "Lỗi hệ thống Win32 API (winerror=%s): %s",
            getattr(exc, "winerror", "N/A"),
            exc,
        )
        return 1
    except Exception as exc:
        logger.exception("Lỗi không xác định trong quá trình thực thi: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
