# -*- coding: UTF-8 -*-


from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

__all__ = ["NCMRC4", "NCMAES"]


class NCMRC4:
    """RC4 for ncm file."""

    def __init__(self, key: bytes) -> None:
        """
        Args:
            key (bytes): RC4 key bytes
        """

        self._key = key
        self._s_box = bytearray(range(256))
        self._key_box = bytearray(256)
        self._key_pos = 0

        # standard RC4 init
        j = 0
        for i in range(256):
            j = (j + self._s_box[i] + self._key[i % len(self._key)]) & 0xFF
            self._s_box[i], self._s_box[j] = self._s_box[j], self._s_box[i]

        # non-standard keybox generate
        for i in range(256):
            j = (i + 1) & 0xFF
            s_j = self._s_box[j]
            s_jj = self._s_box[(s_j + j) & 0xFF]
            self._key_box[i] = self._s_box[(s_jj + s_j) & 0xFF]

    def decrypt(self, ciphertext: bytes) -> bytes:
        """decrypt

        Args:
            ciphertext (bytes): btyes to be decrypted

        Returns:
            bytes: plaintext
        """

        plaintext = bytearray()
        for b in ciphertext:
            plaintext.append(b ^ self._key_box[self._key_pos])
            if self._key_pos >= 255:
                self._key_pos = 0
            else:
                self._key_pos += 1
        return bytes(plaintext)


class NCMAES:
    """AES128 (ECB mode) for ncm file."""

    def __init__(self, key: bytes) -> None:
        """
        Args:
            key (bytes): AES128 key bytes
        """

        assert len(key) == 16
        self._key = key

        self._cryptor = AES.new(self._key, AES.MODE_ECB)

    def decrypt(self, ciphertext: bytes) -> bytes:
        """decrypt

        Args:
            ciphertext (bytes): btyes to be decrypted

        Returns:
            bytes: plaintext
        """

        return self._cryptor.decrypt(ciphertext)

    def unpad(self, padded_data: bytes) -> bytes:
        """unpad (pkcs7) for AES plain text.

        Args:
            padded_data (bytes): data decrypted by NCMAES

        Returns:
            bytes: unpadded data.
        """

        return unpad(padded_data, len(self._key), "pkcs7")
