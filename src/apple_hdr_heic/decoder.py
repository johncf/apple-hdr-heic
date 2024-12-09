import argparse
from pathlib import Path

import colour
import cv2
import OpenEXR
import pillow_heif
from pillow_heif import HeifFile

from apple_hdr_heic import clipped_colorspace_transform, load_as_displayp3_linear, quantize_bt2020_to_bt2100_pq
from apple_hdr_heic.lib import REF_WHITE_LUM

COLORSPACE_CHOICES = list(colour.RGB_COLOURSPACES.keys())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="apple-hdr-heic-decoder",
        description=(
            "Decode an HEIC image file containing HDR gain map and other metadata (in Apple's format) to "
            "a 16-bit per channel (48-bit) PNG file, a 10- or 12-bit HEIC or AVIF file, or a 16- or 32-bit EXR file."
        ),
    )
    parser.add_argument("input_image", help="Input HEIC image path")
    parser.add_argument("output_image", help="Output image path (supports: .png, .heic, .avif, .exr)")
    parser.add_argument(
        "-q", "--quality", type=int, default=-1,
        help="Output image quality; 0 = lowest; 100 = highest; ignored for .png and .exr (default: lossless, see readme)",
    )  # fmt: skip
    parser.add_argument(
        "-b", "--bitdepth", type=int, default=None, choices=[10, 12, 16, 32],
        help="Output channel bit-depth (choices: .avif/.heic [10, 12], .png [16], .exr [16, 32]) (default: lowest)",
    )  # fmt: skip
    parser.add_argument(
        "-y", "--yuv", type=str, default=None, choices=["420", "422", "444"],
        help="Output chroma subsampling; ignored for .png (default: 420)",
    )  # fmt: skip
    parser.add_argument(
        "--colorspace", type=str, default="ITU-R BT.2020", choices=COLORSPACE_CHOICES,
        help="Output color space; only relevant for .exr (default: ITU-R BT.2020)",
    )  # fmt: skip
    args = parser.parse_args()

    assert args.input_image.lower().endswith(".heic")
    assert -1 <= args.quality <= 100
    dp3_linear = load_as_displayp3_linear(args.input_image)
    output_ext = Path(args.output_image).suffix.lower()
    if output_ext == ".exr":
        rgb_linear = clipped_colorspace_transform(dp3_linear, "Display P3", args.colorspace)
        bitdepth = checked_bitdepth(args.bitdepth, [16, 32])
        write_exr(args.output_image, rgb_linear, bitdepth=bitdepth, colorspace=args.colorspace)
        return
    bt2020_linear = clipped_colorspace_transform(dp3_linear, "Display P3", "ITU-R BT.2020")
    bt2100_pq = quantize_bt2020_to_bt2100_pq(bt2020_linear)
    if output_ext == ".png":
        bitdepth = checked_bitdepth(args.bitdepth, [16])
        write_png(args.output_image, bt2100_pq)
    elif output_ext in {".avif", ".heic"}:
        format = "HEIF" if output_ext == ".heic" else "AVIF"
        bitdepth = checked_bitdepth(args.bitdepth, [10, 12])
        write_heif(
            args.output_image,
            bt2100_pq,
            format=format,
            quality=args.quality,
            bitdepth=bitdepth,
            yuv=args.yuv,
        )
    else:
        raise ValueError(f"Output file type not supported: {output_ext}")


def checked_bitdepth(bitdepth: int | None, choices: list[int]) -> int:
    if bitdepth is None:
        return choices[0]
    elif bitdepth not in choices:
        raise ValueError(f"Output bit-depth not supported: {bitdepth} (choose from: {choices})")
    return bitdepth


def write_png(out_path, rgb_data):
    cv2.imwrite(out_path, rgb_data[:, :, ::-1])
    # note: currently Pillow doesn't support 16-bit per channel RGB images
    #       see https://github.com/python-pillow/Pillow/issues/1888
    # note: adding cICP data to PNG files (to indicate BT.2100 PQ) is difficult
    #       see https://github.com/w3c/png/issues/312
    #       see https://github.com/pnggroup/libpng/issues/508
    #       see https://github.com/randy408/libspng/issues/218


def write_heif(out_path, rgb_data, format="HEIF", quality=-1, bitdepth=10, yuv=None):
    if bitdepth == 12:
        pillow_heif.options.SAVE_HDR_TO_12_BIT = True
    imsize = (rgb_data.shape[1], rgb_data.shape[0])
    heif_file = HeifFile()
    added_image = heif_file.add_frombytes(
        mode="RGB;16",
        size=imsize,
        data=bytes(rgb_data),
    )
    added_image.info["color_primaries"] = 9
    added_image.info["transfer_characteristics"] = 16
    added_image.info["matrix_coefficients"] = 9
    added_image.info["full_range_flag"] = 1
    heif_file.save(out_path, format=format, quality=quality, chroma=yuv)


def write_exr(out_path, rgb_data, bitdepth=16, colorspace="ITU-R BT.2020"):
    primaries = colour.RGB_COLOURSPACES[colorspace].primaries
    whitepoint = colour.RGB_COLOURSPACES[colorspace].whitepoint
    rgb_data *= REF_WHITE_LUM / 100  # change white luminance at RGB(1.0, 1.0, 1.0) to 100
    if bitdepth == 16:
        rgb_data = rgb_data.astype("float16")
    channels = {"RGB": rgb_data}
    header = {
        "compression": OpenEXR.ZIP_COMPRESSION,
        "type": OpenEXR.scanlineimage,
        "chromaticities": (*primaries.flatten().tolist(), *whitepoint.tolist()),
        "whiteLuminance": 100.0,
    }
    with OpenEXR.File(header, channels) as outfile:
        outfile.write(out_path)


if __name__ == "__main__":
    main()
