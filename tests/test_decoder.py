import subprocess
from pathlib import Path

ENTRYPOINT = "apple-hdr-heic-decoder"
TEST_FILE = Path(__file__).parent / "data/hdr-sample.heic"


def test_help():
    subp = subprocess.run([ENTRYPOINT, "--help"])
    assert subp.returncode == 0


def _output_format_test(output_format: str, q=None, b=None, y=None, colorspace=None):
    assert output_format in {"png", "heic", "avif", "exr"}
    outfile = Path(f"/tmp/hdr-out.{output_format}")
    assert not outfile.exists()
    args: list[str | Path] = [ENTRYPOINT, TEST_FILE, outfile]
    if q is not None:
        args.extend(["-q", str(q)])
    if b is not None:
        args.extend(["-b", str(b)])
    if y is not None:
        args.extend(["-y", str(y)])
    if colorspace is not None:
        args.extend(["--colorspace", colorspace])
    subp = subprocess.run(args)
    assert subp.returncode == 0
    assert outfile.exists()
    outfile.unlink()


def test_png():
    _output_format_test("png")


def test_heic():
    _output_format_test("heic")
    _output_format_test("heic", q=99, b=10, y=422)
    _output_format_test("heic", q=100, b=12, y=444)


def test_avif():
    _output_format_test("avif")
    _output_format_test("avif", q=99, b=10, y=422)
    _output_format_test("avif", q=100, b=12, y=444)


def test_exr():
    _output_format_test("exr")
    _output_format_test("exr", b=16, colorspace="ROMM RGB")
    _output_format_test("exr", b=32, colorspace="Display P3")
