# ncmdump-py

A simple package used to dump ncm files to mp3 or flac files, it can:

- Decrypt and dump `.ncm` files.
- Auto add album and cover info into `.mp3` or `.flac` files.
- Auto try download cover image when there is no cover data in `.ncm` files.

## Install

```bat
pip install ncmdump-py
```

## Usage

### Command-line tool

```plain
python -m ncmdump [-h] [--in-folder IN_FOLDER] [--out-folder OUT_FOLDER] [--dump-metadata] [--dump-cover] [files ...]
```

```plain
usage: ncmdump [-h] [--in-folder IN_FOLDER] [--out-folder OUT_FOLDER] [--dump-metadata] [--dump-cover] [files ...]

Dump ncm files with progress bar and logging info, only process files with suffix '.ncm'

positional arguments:
  files                 Files to dump, can follow multiple files.

optional arguments:
  -h, --help            show this help message and exit
  --in-folder IN_FOLDER
                        Input folder of files to dump.
  --out-folder OUT_FOLDER
                        Output folder of files dumped.
  --dump-metadata       Whether dump metadata.
  --dump-cover          Whether dump album cover.
```

### Import in your code

```python
from ncmdump import NeteaseCloudMusicFile

ncmfile = NeteaseCloudMusicFile("filename.ncm")
ncmfile.decrypt()

print(ncmfile.music_metadata)  # show music metadata

ncmfile.dump_music("filename.mp3")  # auto detect correct suffix

# Maybe you also need dump metadata or cover image
# ncmfile.dump_metadata("filename.json")  
# ncmfile.dump_cover("filename.jpeg")
```

---

*If you think this project is helpful to you, :star: it and let more people see!*
