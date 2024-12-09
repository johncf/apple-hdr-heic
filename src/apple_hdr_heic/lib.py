import os
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pillow_heif

from apple_hdr_heic.metadata import AppleHDRMetadata

os.environ["COLOUR_SCIENCE__FILTER_USAGE_WARNINGS"] = "True"
os.environ["COLOUR_SCIENCE__DEFAULT_FLOAT_DTYPE"] = "float32"

import colour  # may raise a missing matplotlib warning

REF_WHITE_LUM = 203.0  # reference white luminance in nits
FloatNDArray = npt.NDArray[np.floating]


# ref https://developer.apple.com/documentation/appkit/images_and_pdf/applying_apple_hdr_effect_to_your_photos
def apply_hdrgainmap(
    dp3_sdr: FloatNDArray,
    hdrgainmap: FloatNDArray,
    headroom: float,
) -> FloatNDArray:
    """
    Combine a (non-linear) Display P3 SDR image with its HDR gain map.

    :param dp3_sdr: A numpy array of shape (H, W, 3) with values between 0 and 1.
    :param hdrgainmap: A numpy array of shape (H, W) with values between 0 and 1.
    :param headroom: The value returned by compute_headroom method of AppleHDRMetadata.

    :returns: A numpy array of shape (H, W, 3) with values between 0 and ``headroom``.
    :exception AssertionError: if height and width of ``dp3_sdr`` does not match that of ``hdrgainmap``.
    """
    assert np.issubdtype(dp3_sdr.dtype, np.floating)
    assert np.issubdtype(hdrgainmap.dtype, np.floating)
    # note: Display P3 and sRGB have the same EOTF
    dp3_sdr_linear = colour.models.eotf_sRGB(dp3_sdr)
    assert dp3_sdr.shape[:2] == hdrgainmap.shape
    assert headroom >= 1.0
    hdrgainmap_linear = colour.models.eotf_sRGB(hdrgainmap)
    scale_factor_map = 1.0 + (headroom - 1.0) * hdrgainmap_linear  # between 1.0 and headroom
    dp3_hdr_linear = dp3_sdr_linear * scale_factor_map[:, :, None]
    return dp3_hdr_linear


def clipped_colorspace_transform(
    rgb_linear: FloatNDArray, input_space_name: str, output_space_name: str
) -> FloatNDArray:
    """
    Converts an image from a given linear color space to another linear color space, using simple linear transformation.

    :param rgb_linear: A numpy array of shape (H, W, 3).
    :param input_space_name: The name of the linear color space that ``rgb_linear`` is in.
    :param output_space_name: The name of the linear color space that ``rgb_linear`` should be transformed to.

    :returns: A numpy array of shape (H, W, 3) after linear color space transformation of ``rgb_linear``,
        with negative values truncated to zero.
    """
    assert np.issubdtype(rgb_linear.dtype, np.floating)
    assert input_space_name in colour.RGB_COLOURSPACES
    assert output_space_name in colour.RGB_COLOURSPACES
    input_space = colour.RGB_COLOURSPACES[input_space_name]
    output_space = colour.RGB_COLOURSPACES[output_space_name]
    transform_matrix = colour.matrix_RGB_to_RGB(input_space, output_space).astype(rgb_linear.dtype)
    outrgb_linear = np.tensordot(rgb_linear, transform_matrix, axes=(2, 1))
    return np.clip(outrgb_linear, 0.0, None, out=outrgb_linear)


def load_primary_and_aux(file_name: str | Path, aux_type: str) -> tuple[FloatNDArray, FloatNDArray]:
    """
    Loads the primary image and the auxiliary image of the specified aux_type from an HEIC file.

    :param file_name: A path to an HEIC image file containing HDR gain map data.

    :returns: A tuple of float32 numpy arrays: (primary, aux)
    """
    heif_file = pillow_heif.open_heif(file_name)
    assert aux_type in heif_file.info["aux"]
    aux_id = heif_file.info["aux"][aux_type][0]
    aux_im = heif_file.get_aux_image(aux_id)
    return np.asarray(heif_file) / np.float32(255), np.asarray(aux_im) / np.float32(255)


def load_as_displayp3_linear(file_name: str | Path) -> FloatNDArray:
    """
    Loads an HEIC file and returns the HDR image in linear Display P3 color space.

    :param file_name: A path to an HEIC image file containing HDR gain map data.

    :returns: A float32 numpy array of shape (H, W, 3) in linear Display P3 color space.
    """
    hdr_metadata = AppleHDRMetadata.from_file(file_name)
    assert hdr_metadata.profile_desc == "Display P3"
    aux_type = hdr_metadata.aux_type or "urn:com:apple:photo:2020:aux:hdrgainmap"
    headroom = hdr_metadata.compute_headroom()

    dp3_sdr, hdrgainmap = load_primary_and_aux(file_name, aux_type)
    image_size = dp3_sdr.shape[1], dp3_sdr.shape[0]
    hdrgainmap = cv2.resize(hdrgainmap, image_size, interpolation=cv2.INTER_LANCZOS4)  # type: ignore
    np.clip(hdrgainmap, 0.0, 1.0, out=hdrgainmap)

    return apply_hdrgainmap(dp3_sdr, hdrgainmap, headroom)


def load_as_bt2020_linear(file_name: str | Path) -> FloatNDArray:
    """
    Loads an HEIC file and returns the HDR image in linear BT.2020 color space.

    :param file_name: A path to an HEIC image file containing HDR gain map data.

    :returns: A float32 array of shape (H, W, 3) in linear BT.2020 color space, with non-negative values.
    """
    dp3_linear = load_as_displayp3_linear(file_name)
    bt2020_linear = clipped_colorspace_transform(dp3_linear, "Display P3", "ITU-R BT.2020")
    return bt2020_linear


def quantize_bt2020_to_bt2100_pq(
    bt2020_linear: FloatNDArray,
    white_lum: float = REF_WHITE_LUM,
) -> npt.NDArray[np.uint16]:
    """
    Quantize RGB pixel values in linear BT.2020 color space to non-linear BT.2100 PQ color space.

    :param bt2020_linear: A float32 array of shape (H, W, 3) in linear BT.2020 color space, with non-negative values.
    :param white_lum: Luminance of reference white in cd/m2 (or nits). Default: 203 nits

    :returns: A uint16 array of shape (H, W, 3) in non-linear BT.2100 color space with PQ transfer function,
        with values between 0 and 2^16 - 1.
    """
    bt2100_pq = colour.models.eotf_inverse_BT2100_PQ(white_lum * bt2020_linear)
    return quantize_unit_interval_to_uint16(bt2100_pq)


def quantize_unit_interval_to_uint16(float_array: FloatNDArray) -> npt.NDArray[np.uint16]:
    """
    Quantizes a floating point numpy array with values in the unit interval to a 16-bit unsigned integer.

    :param float_array: A floating point numpy array with values between 0 and 1.

    :returns: A uint16 numpy array.
    """
    quantized = float_array * 0xFFFF
    np.round(quantized, out=quantized)
    np.clip(quantized, 0, 0xFFFF, out=quantized)
    return quantized.astype(np.uint16)
