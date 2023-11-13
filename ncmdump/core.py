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

__all__ = ["NeteaseCloudMusicFile"]


class NeteaseCloudMusicFile:
    """ncm file"""

    MAGIC_HEADER = b"CTENFDAM"

    AES_KEY_RC4_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")
    RC4_KEY_XORBYTE = 0x64

    AES_KEY_METADATA = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")
    METADATA_XORBYTE = 0x63

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def file_type(self) -> str:
        """`flac` or `mp3`"""
        return self._metadata.get("format", "")

    @property
    def id(self) -> int:
        return self._metadata.get("musicId", -1)

    @property
    def name(self) -> str:
        return self._metadata.get("musicName", "")

    @property
    def artists(self) -> List[str]:
        return [a[0] for a in self._metadata.get("artist", [])]

    @property
    def album(self) -> str:
        return self._metadata.get("album", "")

    @property
    def cover_data(self) -> bytes:
        return self._cover_data

    @property
    def cover_suffix(self) -> str:
        return f".{imghdr.what(None, self._cover_data[:32])}"

    @property
    def cover_mime(self) -> str:
        return mimetypes.types_map.get(self.cover_suffix, "")

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
            self._metadata = {}

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
            self._metadata: dict

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
        """

        # if no metadata
        if self._metadata_enc_size <= 0:
            self._metadata = {}

        else:
            cryptor = crypto.NCMAES(self.AES_KEY_METADATA)

            metadata = bytes(map(lambda b: b ^ self.METADATA_XORBYTE, self._metadata_enc))

            metadata = b64decode(metadata[len(b"163 key(Don't modify):"):])
            metadata = cryptor.unpad(cryptor.decrypt(metadata))

            self._metadata: dict = json.loads(metadata[len(b"music:"):])

            # if no cover data, try get cover data by url in metadata
            if self._cover_data_size <= 0:
                try:
                    with request.urlopen(self._metadata.get("albumPic", "")) as res:
                        if res.status < 400:
                            self._cover_data = res.read()
                            self._cover_data_size = len(self._cover_data)
                except:
                    pass

    def _decrypt_music_data(self) -> None:
        """
        Attributes:
            self._music_data: bytes
        """

        cryptor = crypto.NCMRC4(self._rc4_key)
        self._music_data = cryptor.decrypt(self._music_data_enc)

    def decrypt(self) -> "NeteaseCloudMusicFile":
        """Decrypt all data.

        Returns:
            self
        """

        self._decrypt_rc4_key()
        self._decrypt_metadata()
        self._decrypt_music_data()

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
        path.write_text(json.dumps(self._metadata, ensure_ascii=False, indent=4), "utf8")
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

        path = path.with_suffix(self.cover_suffix)
        path.write_bytes(self._cover_data)
        return path

    def _dump_music(self, path: Union[str, PathLike]) -> Path:
        """Dump music without any other info."""

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path = path.with_suffix(f".{self.file_type}")
        path.write_bytes(self._music_data)
        return path

    def _addinfo_mp3(self, path: Union[str, PathLike]) -> None:
        """Add info for mp3 format."""

        audio = mp3.MP3(path)

        audio["TIT2"] = id3.TIT2(text=self.name, encoding=id3.Encoding.UTF8)  # title
        audio["TALB"] = id3.TALB(text=self.album, encoding=id3.Encoding.UTF8)  # album
        audio["TPE1"] = id3.TPE1(text="/".join(self.artists), encoding=id3.Encoding.UTF8)  # artists
        audio["TPE2"] = id3.TPE2(text="/".join(self.artists), encoding=id3.Encoding.UTF8)  # album artists

        if self._cover_data_size > 0:
            audio["APIC"] = id3.APIC(type=id3.PictureType.COVER_FRONT, mime=self.cover_mime, data=self._cover_data)  # cover

        audio.save()

    def _addinfo_flac(self, path: Union[str, PathLike]) -> None:
        """Add info for flac format."""

        audio = flac.FLAC(path)

        # add music info
        audio["title"] = self.name
        audio["artist"] = self.artists
        audio["album"] = self.album
        audio["albumartist"] = "/".join(self.artists)

        # add cover
        if self._cover_data_size > 0:
            cover = flac.Picture()
            cover.type = id3.PictureType.COVER_FRONT
            cover.data = self._cover_data

            with BytesIO(self._cover_data) as data:
                with Image.open(data) as f:
                    cover.mime = self.cover_mime
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

        if self.file_type == "flac":
            self._addinfo_flac(path)
        elif self.file_type == "mp3":
            self._addinfo_mp3(path)
        else:
            raise NotImplementedError(f"Unknown file type '{self.file_type}', failded to add music info.")

        return path
