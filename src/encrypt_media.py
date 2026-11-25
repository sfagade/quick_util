#!/usr/bin/env python3
import argparse
import os
import struct
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"MENC1"
SALT_SIZE = 16
NONCE_SIZE = 12  # Recommended size for GCM
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunks


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=32,  # 256-bit key
        n=2**14,
        r=8,
        p=1,
    )
    return kdf.derive(password.encode("utf-8"))


def build_nonce(base_nonce: bytes, counter: int) -> bytes:
    # Derive a unique per-chunk nonce by XORing the last 8 bytes with a counter
    counter_bytes = struct.pack(">Q", counter)
    nonce = bytearray(base_nonce)
    for i in range(8):
        nonce[NONCE_SIZE - 8 + i] ^= counter_bytes[i]
    return bytes(nonce)


def encrypt_media(input_path: Path, output_path: Path, password: str) -> None:
    salt = os.urandom(SALT_SIZE)
    base_nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    ext_bytes = input_path.suffix.lower().encode("utf-8")
    if len(ext_bytes) > 255:
        raise ValueError("File extension is too long to store in header.")

    total_size = input_path.stat().st_size
    processed = 0

    with input_path.open("rb") as fin, output_path.open("wb") as fout:
        # Header: MAGIC (5B) + SALT (16B) + BASE_NONCE (12B) + EXT_LEN (1B) + EXT (ext_len B)
        fout.write(MAGIC + salt + base_nonce + struct.pack(">B", len(ext_bytes)) + ext_bytes)

        counter = 0
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break

            nonce = build_nonce(base_nonce, counter)
            ciphertext = aesgcm.encrypt(nonce, chunk, None)
            fout.write(struct.pack(">I", len(ciphertext)) + ciphertext)

            counter += 1
            processed += len(chunk)
            pct = (processed / total_size * 100) if total_size else 100.0
            print(f"\rEncrypting: {pct:.1f}%", end="", flush=True)

    print(f"\nDone -> {output_path}")


def decrypt_media(input_path: Path, output_path: Path, password: str) -> None:
    with input_path.open("rb") as fin:
        magic = fin.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("Invalid file format or missing MENC1 header.")

        salt = fin.read(SALT_SIZE)
        base_nonce = fin.read(NONCE_SIZE)
        ext_len_byte = fin.read(1)
        if len(salt) != SALT_SIZE or len(base_nonce) != NONCE_SIZE or len(ext_len_byte) != 1:
            raise ValueError("Corrupted or truncated header.")

        (ext_len,) = struct.unpack(">B", ext_len_byte)
        orig_ext = fin.read(ext_len).decode("utf-8", errors="replace")
        if len(orig_ext.encode("utf-8")) != ext_len:
            raise ValueError("Corrupted extension in header.")

        # If user didn't include an extension on output_path, restore the original one
        if not output_path.suffix and orig_ext:
            output_path = output_path.with_suffix(orig_ext)

        key = derive_key(password, salt)
        aesgcm = AESGCM(key)

        with output_path.open("wb") as fout:
            counter = 0
            while True:
                len_bytes = fin.read(4)
                if not len_bytes:
                    break
                if len(len_bytes) != 4:
                    raise ValueError("Truncated chunk length prefix.")

                (chunk_len,) = struct.unpack(">I", len_bytes)
                ciphertext = fin.read(chunk_len)
                if len(ciphertext) != chunk_len:
                    raise ValueError("Truncated or corrupted encrypted chunk.")

                nonce = build_nonce(base_nonce, counter)
                try:
                    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                except Exception as exc:
                    raise ValueError("Decryption failed: wrong password or tampered data.") from exc

                fout.write(plaintext)
                counter += 1

    print(f"Done -> {output_path}")


def path_walker(
    file_path: Path,
    extensions,
    password: str,
    apply: bool = False,
) -> None:
    print(f"Inside walker: {file_path}")

    for path in file_path.rglob("*"):
        if not path.is_file():
            continue

        file_name = f"{path.stem}"
        file_type = path.suffix
        print(f"Found {file_name} -- {file_type}")

        if file_type in extensions:
            if apply:
                print(f"Will encrypt file now")
                encrypt_media(path, path.with_name(f'{file_name}.enc'), password)
        else:
            print(f"Ignoring file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt or decrypt video and picture files using AES-256-GCM.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enc = subparsers.add_parser("encrypt", help="Encrypt a video or picture file")
    enc.add_argument("input", type=Path, help="Target folder")
    enc.add_argument(
        "output",
        type=Path,
        help="Output decrypted file path (extension auto-restored if omitted)",
    )
    enc.add_argument(
        "--extensions",
        nargs="+",  # Use "*" to allow 0 or more; "+" requires at least 1
        default=[],
        help="Media type by extension",
    )
    enc.add_argument("--password", required=True, help="Encryption password")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename files (without this flag, only prints a dry run)",
    )

    dec = subparsers.add_parser("decrypt", help="Decrypt a video or picture file")
    dec.add_argument("input", type=Path, help="Input encrypted file path")
    dec.add_argument(
        "output",
        type=Path,
        help="Output decrypted file path (extension auto-restored if omitted)",
    )
    dec.add_argument("--password", required=True, help="Decryption password")

    args = parser.parse_args()

    try:
        if args.command == "encrypt":
            if (
                not args.input.is_dir() and not args.input.is_file()
            ):  # when encrypting input can either be a file or a folder
                raise SystemExit(f"Error: '{args.input}' does not exist.")

            if args.input.is_dir():
                print(f"Encrypting all media files in {args.input}")
                if not args.extensions:
                    raise SystemExit(f"Error: Extensions is required for folder encrypt.")
                path_walker(args.input, args.extensions, args.password)
            else:
                encrypt_media(args.input, args.output, args.password)
        elif args.command == "decrypt":
            if not args.input.is_file():  # when decrypting we need input to be a file
                raise SystemExit(f"Error: '{args.input}' does not exist.")
            decrypt_media(args.input, args.output, args.password)
    except ValueError as err:
        raise SystemExit(f"Error: {err}") from err


if __name__ == "__main__":
    main()
