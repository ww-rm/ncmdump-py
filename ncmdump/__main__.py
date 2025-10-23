import traceback
from argparse import ArgumentParser
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ncmdump import NeteaseCloudMusicFile, __version__
from ncmdump.logger import console, logger

if __name__ == "__main__":
    logger.info(f"ncmdump v{__version__}\n")

    parser = ArgumentParser("ncmdump", description="Dump ncm files with progress bar and logging info, only process files with suffix '.ncm'")
    parser.add_argument("files", nargs="*", help="Files to dump, can follow multiple files.")
    parser.add_argument("--in-folder", help="Input folder of files to dump.")
    parser.add_argument("--out-folder", help="Output folder of files dumped.", default=".")

    parser.add_argument("--dump-metadata", help="Whether dump metadata.", action="store_true")
    parser.add_argument("--dump-cover", help="Whether dump album cover.", action="store_true")

    args = parser.parse_args()

    out_folder = Path(args.out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    dump_metadata = args.dump_metadata
    dump_cover = args.dump_cover

    files = args.files
    if args.in_folder:
        files.extend(Path(args.in_folder).iterdir())
    files = list(filter(lambda p: p.suffix == ".ncm", map(Path, files)))

    if not files:
        parser.print_help()
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn("[progress.percentage]{task.completed:d}/{task.total:d}"),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[#d75f00]Dumping files", total=len(files))

            for ncm_path in files:
                output_path = out_folder.joinpath(ncm_path.with_suffix(".mp3"))  # suffix will be corrected later

                try:
                    ncmfile = NeteaseCloudMusicFile(ncm_path).decrypt()
                    music_path = ncmfile.dump_music(output_path)

                    if dump_metadata:
                        ncmfile.dump_metadata(output_path)
                    if dump_cover:
                        ncmfile.dump_cover(output_path)

                except Exception as e:
                    logger.exception(e)
                    logger.error(f"{ncm_path} -> {e}")
                else:
                    if not ncmfile.has_metadata:
                        logger.warning(f"{ncm_path} -> {music_path}, no metadata found")
                    if not ncmfile.has_cover:
                        logger.warning(f"{ncm_path} -> {music_path}, no cover data found")

                finally:
                    progress.advance(task)
