# apple-hdr-heic

A library/tool to decode photos (HEIC files) taken on an iPhone that contain HDR gain map, and convert it to a 48-bit (16-bit per channel) HDR representation as per [Rec. 2100](https://en.wikipedia.org/wiki/Rec._2100) with PQ transfer function.

Disclaimer: This project is NOT affiliated with, or endorsed by, Apple Inc. or any of its subsidiaries.

## Pre-requisites

* Python 3.10+
* [`exiftool`](https://exiftool.org/) 12.54+
  - For Ubuntu or Debian, do `sudo apt install libimage-exiftool-perl`
  - For other Linux distros, search `exiftool` using your package manager
  - For Mac or Windows, follow the instructions in website
  - For Windows, it is also available via [Scoop](https://scoop.sh/)

## Installation

Clone this repository, create a python environment and do:

```
pip install .
```

## Usage

CLI tool:

```
apple-hdr-heic-decode input.heic output.png
```

Library usage:

```py
from apple_hdr_heic import load_as_bt2100_pq, quantize_to_uint16

bt2100_pq = load_as_bt2100_pq("input.heic")
bt2100_pq_u16 = quantize_to_uint16(bt2100_pq)
cv2.imwrite("output.png", bt2100_pq_u16[:, :, ::-1])
```

The output file `output.png` does not contain the necessary [cICP](https://en.wikipedia.org/wiki/Coding-independent_code_points) metadata that denotes it to have `bt2020` (9) color primaries and `smpte2084` (16) transfer characteristics.

To convert the above PNG to a 12-bit HDR AVIF file with appropriate metadata using [libavif](https://github.com/AOMediaCodec/libavif), do:

```
avifenc -s 4 -j 4 --min 1 --max 56 -a end-usage=q -a cq-level=10 -a tune=ssim -a color:enable-qm=1 \
    -a color:enable-chroma-deltaq=1 -d 12 --cicp 9/16/9 output.png output.avif
```
