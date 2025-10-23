# -*- coding: UTF-8 -*-

import imghdr
import json
import mimetypes
from base64 import b64decode
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import List, Union
from urllib import request

from mutagen import flac, id3, mp3
from PIL import Image

from ncmdump import crypto
from ncmdump.logger import logger

__all__ = ["NeteaseCloudMusicFile", "Metadata", "MusicMetadata"]


class MusicMetadata:
    """Metadata for music"""

    def __init__(self, data: dict = None) -> None:
        self._data = data or {}

    def __repr__(self) -> str:
        return self._data.__repr__()

    def __str__(self) -> str:
        return self._data.__str__()

    @property
    def json(self) -> dict:
        return self._data

    @property
    def format(self) -> str:
        return self._data.get("format", "mp3")

    @property
    def id(self) -> int:
        return self._data.get("musicId", -1)

    @property
    def name(self) -> str:
        return self._data.get("musicName", "Unknown")

    @property
    def artists(self) -> List[str]:
        return [a[0] for a in self._data.get("artist", [])]

    @property
    def album(self) -> str:
        return self._data.get("album", "Unknown")

    @property
    def cover_url(self) -> str:
        return self._data.get("albumPic", "http://p3.music.126.net/tBTNafgjNnTL1KlZMt7lVA==/18885211718935735.jpg")


class Metadata:
    """Metadata for ncm file.

    `music`:

    ```json
    {
        "format": "flac", 
        "musicId": 431259256, 
        "musicName": "カタオモイ", 
        "artist": [["Aimer", 16152]], 
        "album": "daydream", 
        "albumId": 34826361, 
        "albumPicDocId": 109951165052089697, 
        "albumPic": "http://p1.music.126.net/2QRYxUqXfW0zQpm2_DVYRA==/109951165052089697.jpg", 
        "mvId": 0, 
        "flag": 4, 
        "bitrate": 876923, 
        "duration": 207866, 
        "alias": [], 
        "transNames": ["单相思"]
    }
    ```

    `dj`:

    ```json
    {
        "programId": 2506516081,
        "programName": "03 踏遍万水千山",
        "mainMusic": {
            "musicId": 1957438579,
            "musicName": "03 踏遍万水千山",
            "artist": [],
            "album": "[DJ节目]北方文艺出版社的DJ节目 第8期",
            "albumId": 0,
            "albumPicDocId": 109951167551086981,
            "albumPic": "https://p1.music.126.net/M48NPuT591tIqqUdQyKZlg==/109951167551086981.jpg",
            "mvId": 0,
            "flag": 0,
            "bitrate": 320000,
            "duration": 1222948,
            "alias": [],
            "transNames": []
        },
        "djId": 7891086863,
        "djName": "北方文艺出版社",
        "djAvatarUrl": "http://p1.music.126.net/DQr2q_S23tYY8vU_C-kAYw==/109951167535553901.jpg",
        "createTime": 1655691020376,
        "brand": "林徽因传：倾我所能去坚强",
        "serial": 3,
        "programDesc": "这是一本有温度、有态度的传记，记录了真正意义上的民国女神——林徽因，从容坚强、传奇丰沛的一生。",
        "programFeeType": 15,
        "programBuyed": true,
        "radioId": 977264730,
        "radioName": "林徽因传：倾我所能去坚强",
        "radioCategory": "文学出版",
        "radioCategoryId": 3148096,
        "radioDesc": "这是一本有温度、有态度的传记，记录了真正意义上的民国女神——林徽因，从容坚强、传奇丰沛的一生。",
        "radioFeeType": 1,
        "radioFeeScope": 0,
        "radioBuyed": true,
        "radioPrice": 30,
        "radioPurchaseCount": 0
    }
    ```

    """

    def __init__(self, metadata: bytes = b"") -> None:
        self._metadata = metadata or b"music:{}"

        self._type = self._metadata[:self._metadata.index(b":")].decode()
        self._data: dict = json.loads(self._metadata[self._metadata.index(b":") + 1:])

        if self.type == "music":
            self._music_metadata = MusicMetadata(self._data)
        elif self.type == "dj":
            self._music_metadata = MusicMetadata(self._data.get("mainMusic"))
        else:
            raise TypeError(f"Unknown metadata type: '{self.type}'")

    def __repr__(self) -> str:
        return self._data.__repr__()

    def __str__(self) -> str:
        return self._data.__str__()

    @property
    def type(self) -> str:
        return self._type

    @property
    def json(self) -> dict:
        return self._data

    @property
    def music_metadata(self) -> MusicMetadata:
        return self._music_metadata


class NeteaseCloudMusicFile:
    """ncm file"""

    MAGIC_HEADER = b"CTENFDAM"

    AES_KEY_RC4_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")
    RC4_KEY_XORBYTE = 0x64

    AES_KEY_METADATA = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")
    METADATA_XORBYTE = 0x63

    @property
    def has_metadata(self) -> bool:
        return self._metadata_enc_size > 0

    @property
    def has_cover(self) -> bool:
        return self._cover_data_size > 0

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    @property
    def music_metadata(self) -> MusicMetadata:
        return self._metadata.music_metadata

    @property
    def _cover_suffix(self) -> str:
        return f".{imghdr.what(None, self._cover_data[:32])}"

    @property
    def _cover_mime(self) -> str:
        return mimetypes.types_map.get(self._cover_suffix, "")

    def __init__(self, path: Union[str, PathLike]) -> None:
        """
        Args:
            path (str or PathLike): ncm file path
        """

        self._path = Path(path)
        self._parse()

    def _parse(self) -> None:
        """parse file."""

        with self._path.open("rb") as ncmfile:
            self._hdr = ncmfile.read(8)

            if self._hdr != self.MAGIC_HEADER:
                raise TypeError(f"{self._path} is not a valid ncm file.")

            # XXX: 2 bytes unknown
            self._gap1 = ncmfile.read(2)

            self._rc4_key_enc_size = int.from_bytes(ncmfile.read(4), "little")
            self._rc4_key_enc = ncmfile.read(self._rc4_key_enc_size)
            self._rc4_key = b""

            self._metadata_enc_size = int.from_bytes(ncmfile.read(4), "little")
            self._metadata_enc = ncmfile.read(self._metadata_enc_size)
            self._metadata = Metadata(b"")

            # XXX: 9 bytes unknown
            self._crc32 = int.from_bytes(ncmfile.read(4), "little")
            self._gap2 = ncmfile.read(5)

            self._cover_data_size = int.from_bytes(ncmfile.read(4), "little")
            self._cover_data = ncmfile.read(self._cover_data_size)

            self._music_data_enc = ncmfile.read()
            self._music_data = b""

    def _decrypt_rc4_key(self) -> None:
        """
        Attributes:
            self._rc4_key: bytes
        """

        cryptor = crypto.NCMAES(self.AES_KEY_RC4_KEY)

        rc4_key = bytes(map(lambda b: b ^ self.RC4_KEY_XORBYTE, self._rc4_key_enc))
        rc4_key = cryptor.unpad(cryptor.decrypt(rc4_key))

        self._rc4_key = rc4_key[len(b"neteasecloudmusic"):]

    def _decrypt_metadata(self) -> None:
        """
        Attributes:
            self._metadata: Metadata
        """

        # if no metadata
        if self._metadata_enc_size > 0:
            cryptor = crypto.NCMAES(self.AES_KEY_METADATA)

            metadata = bytes(map(lambda b: b ^ self.METADATA_XORBYTE, self._metadata_enc))

            metadata = b64decode(metadata[len(b"163 key(Don't modify):"):])
            metadata = cryptor.unpad(cryptor.decrypt(metadata))

            self._metadata = Metadata(metadata)

    def _decrypt_music_data(self) -> None:
        """
        Attributes:
            self._music_data: bytes
        """

        cryptor = crypto.NCMRC4(self._rc4_key)
        self._music_data = cryptor.decrypt(self._music_data_enc)

    def _try_get_cover_data(self) -> int:
        """If no cover data, try get cover data by url in metadata"""

        if self._cover_data_size <= 0:
            try:
                with request.urlopen(self._metadata.music_metadata.cover_url) as res:
                    if res.status < 400:
                        self._cover_data = res.read()
                        self._cover_data_size = len(self._cover_data)
            except:
                pass

        return self._cover_data_size

    def decrypt(self) -> "NeteaseCloudMusicFile":
        """Decrypt all data.

        Returns:
            self
        """

        self._decrypt_rc4_key()
        self._decrypt_metadata()

        self._try_get_cover_data()

        return self

    def dump_metadata(self, path: Union[str, PathLike], suffix: str = ".json") -> Path:
        """Dump metadata.

        Args:
            path (str or PathLike): path to dump.
            suffix (str): suffix for path, default to `.json`

        Returns:
            Path: path dumped.
        """

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = path.with_suffix(suffix)
        path.write_text(json.dumps(self._metadata.json, ensure_ascii=False, indent=4), "utf8")
        return path

    def dump_cover(self, path: Union[str, PathLike]) -> Path:
        """Dump cover image.

        Args:
            path (str or PathLike): path to dump.

        Returns:
            Path: path dumped.

        Note:
            If no cover data found, an empty file will be dumped, with same file stem and `None` suffix.
        """

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = path.with_suffix(self._cover_suffix)
        path.write_bytes(self._cover_data)
        return path

    def _dump_music(self, path: Union[str, PathLike]) -> Path:
        """Dump music without any other info."""

        # lazy decrypt
        if not self._music_data:
            self._decrypt_music_data()

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = path.with_suffix(f".{self._metadata.music_metadata.format}")
        path.write_bytes(self._music_data)
        return path

    def _addinfo_mp3(self, path: Union[str, PathLike]) -> None:
        """Add info for mp3 format, may raise exception."""

        audio = mp3.MP3(path)

        audio["TIT2"] = id3.TIT2(text=self._metadata.music_metadata.name, encoding=id3.Encoding.UTF8)  # title
        audio["TALB"] = id3.TALB(text=self._metadata.music_metadata.album, encoding=id3.Encoding.UTF8)  # album
        audio["TPE1"] = id3.TPE1(text="/".join(self._metadata.music_metadata.artists), encoding=id3.Encoding.UTF8)  # artists
        audio["TPE2"] = id3.TPE2(text="/".join(self._metadata.music_metadata.artists), encoding=id3.Encoding.UTF8)  # album artists

        if self._cover_data_size > 0:
            audio["APIC"] = id3.APIC(type=id3.PictureType.COVER_FRONT, mime=self._cover_mime, data=self._cover_data)  # cover

        audio.save()

    def _addinfo_flac(self, path: Union[str, PathLike]) -> None:
        """Add info for flac format, may raise exception."""

        audio = flac.FLAC(path)

        # add music info
        audio["title"] = self._metadata.music_metadata.name
        audio["artist"] = self._metadata.music_metadata.artists
        audio["album"] = self._metadata.music_metadata.album
        audio["albumartist"] = "/".join(self._metadata.music_metadata.artists)

        # add cover
        if self._cover_data_size > 0:
            cover = flac.Picture()
            cover.type = id3.PictureType.COVER_FRONT
            cover.data = self._cover_data

            with BytesIO(self._cover_data) as data:
                with Image.open(data) as f:
                    cover.mime = self._cover_mime
                    cover.width = f.width
                    cover.height = f.height
                    cover.depth = len(f.getbands()) * 8

            audio.add_picture(cover)

        audio.save()

    def dump_music(self, path: Union[str, PathLike]) -> Path:
        """Dump music with metadata and cover.

        Args:
            path (str or PathLike): path to dump.

        Returns:
            Path: path dumped.

        Raises:
            NotImplementedError: If there are some unknown file types, it will only dump music data without music info.
        """

        path = self._dump_music(path)

        try:

            if self._metadata.music_metadata.format == "flac":
                self._addinfo_flac(path)
            elif self._metadata.music_metadata.format == "mp3":
                self._addinfo_mp3(path)
            else:
                raise NotImplementedError(f"Unknown file type '{self._metadata.music_metadata.format}'")
        except Exception as e:
            logger.warning("Skipped adding music info for '%s', %s", path, e)

        return path
