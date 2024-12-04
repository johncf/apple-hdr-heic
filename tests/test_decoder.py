import subprocess

ENTRYPOINT = "apple-hdr-heic-decoder"


def test_help():
    subp = subprocess.run([ENTRYPOINT, "--help"])
    assert subp.returncode == 0


# TODO test export for each file type
