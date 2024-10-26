import argparse

import cv2

from apple_hdr_heic import load_as_bt2100_pq, quantize_to_uint16


def main():
    parser = argparse.ArgumentParser(
        prog="apple-hdr-heic-decoder",
        description=(
            "Decode an HEIC image file containing HDR gain map and other metadata (in Apple's format) to "
            "a 48-bit PNG file in BT.2100 color space with PQ transfer function."
        ),
    )
    parser.add_argument("input_image", help="Input HEIC image")
    parser.add_argument("output_image", help="Output PNG image")
    args = parser.parse_args()

    assert args.input_image.lower().endswith(".heic")
    assert args.output_image.lower().endswith(".png")
    bt2100_pq = load_as_bt2100_pq(args.input_image)
    bt2100_pq_u16 = quantize_to_uint16(bt2100_pq)
    cv2.imwrite(args.output_image, bt2100_pq_u16[:, :, ::-1])
    # note: currently Pillow doesn't support 16-bit per channel RGB images
    #       see https://github.com/python-pillow/Pillow/issues/1888
    # note: adding cICP data to PNG files (to indicate BT.2100 PQ) is difficult
    #       see https://github.com/w3c/png/issues/312
    #       see https://github.com/pnggroup/libpng/issues/508
    #       see https://github.com/randy408/libspng/issues/218


if __name__ == "__main__":
    main()
