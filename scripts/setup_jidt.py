"""Download the official, checksum-pinned JIDT 1.6.1 library into work/jidt."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.6.1"
URL = "https://github.com/jlizier/jidt/releases/download/v1.6.1/infodynamics-dist-1.6.1.zip"
ARCHIVE_SHA256 = "460914b46c29ec05cbb4424e5b46d5bfd08bdcbbe6c22c40c92b06966fb81d71"
JAR_SHA256 = "2d367c244b729877fdaf0608884cf97ae964a8035c3020215b799812143a5b11"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ensure_jidt():
    folder = ROOT / "work/jidt"
    folder.mkdir(parents=True, exist_ok=True)
    jar = folder / "infodynamics.jar"
    if jar.exists():
        if digest(jar) != JAR_SHA256:
            raise ValueError("JIDT jar checksum mismatch; remove the incorrect work/jidt/infodynamics.jar")
        return jar
    archive = folder / "infodynamics-dist-1.6.1.zip"
    if not archive.exists():
        request = urllib.request.Request(URL, headers={"User-Agent": "GSclone-JIDT-setup"})
        temporary = archive.with_suffix(".download")
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if digest(temporary) != ARCHIVE_SHA256:
            raise ValueError("JIDT archive checksum mismatch")
        temporary.replace(archive)
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError("JIDT archive checksum mismatch")
    with zipfile.ZipFile(archive) as source:
        contents = source.read("infodynamics.jar")
    if hashlib.sha256(contents).hexdigest() != JAR_SHA256:
        raise ValueError("JIDT jar checksum mismatch")
    jar.write_bytes(contents)
    return jar


if __name__ == "__main__":
    print(ensure_jidt())
