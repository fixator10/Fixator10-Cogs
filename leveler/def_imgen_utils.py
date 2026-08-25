import operator
import os
import random
import traceback
import warnings
from io import BytesIO
from logging import getLogger
from math import floor, log
from pathlib import Path
from typing import Literal, Optional, Union

from redbot.core.data_manager import cog_data_path
from redbot.core.errors import CogLoadError

from .abc import MixinMeta

try:
    from PIL import Image, ImageDraw
    from PIL import features as pil_features
except Exception as e:
    raise CogLoadError(
        f"Can't load pillow: {e}\n"
        "Please follow next steps on wiki: "
        "https://github.com/fixator10/Fixator10-Cogs/wiki/"
        "Installing-Leveler#my-bot-throws-error-on-load-something-related-to-pillow."
    )

try:
    from PIL import Image

    LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    from PIL.Image import LANCZOS

try:
    import numpy
    from scipy import cluster
except Exception as e:
    warnings.warn(
        "numpy/scipy is unable to import. Autocolor feature will be not available. Traceback:\n"
        f"{''.join(traceback.format_exception_only(type(e), e))}",
        RuntimeWarning,
    )


logger = getLogger("red.fixator10-cogs.leveler")
SAVE_FORMAT = "webp" if pil_features.check("webp") else "png"


class DefaultImageGeneratorsUtils(MixinMeta):
    """Utils for default image generators"""

    async def _check_image_exists(
        self, image_name: str, *, guild_id: Optional[Union[Literal["global"], int]] = None
    ) -> Optional[Path]:
        ret = None
        if guild_id is not None:
            path = cog_data_path(self).joinpath(str(guild_id))
            if not path.is_dir():
                path.mkdir(exist_ok=True, parents=True)
            path = path.joinpath(image_name)
            if os.path.isfile(path) and os.path.getsize(path) != 0:
                ret = path

        global_path = cog_data_path(self).joinpath("global")
        if not global_path.is_dir():
            global_path.mkdir(exist_ok=True, parents=True)
        global_path = global_path.joinpath(image_name)

        if os.path.isfile(global_path) and os.path.getsize(global_path) != 0:
            ret = global_path
        return ret

    async def _download_image(
        self, url: str, *, guild_id: Optional[Union[Literal["global"], int]] = None
    ) -> BytesIO:
        filename = url.split("/")[-1]
        path = await self._check_image_exists(filename, guild_id=guild_id)
        if path is not None:
            logger.debug("Image %s exists, returning saved version", filename)
            with path.open("rb") as infile:
                image = BytesIO(infile.read())
            return image
        async with self.session.get(url) as r:
            logger.debug("Image %s missing, downloading now", filename)
            image = BytesIO(await r.content.read())
            try:
                im = Image.open(image).convert("RGBA")
            except IOError:
                raise TypeError("The url provided is not a valid image")
            guild_path = "global" if guild_id is None else str(guild_id)
            path = cog_data_path(self).joinpath(guild_path)
            if not path.is_dir():
                path.mkdir(exist_ok=True, parents=True)
            path = path.joinpath(filename)
            with path.open("wb") as outfile:
                im.save(outfile, format=SAVE_FORMAT)
        return image

    async def _valid_image_url(
        self, url: str, *, guild_id: Optional[Union[Literal["global"], int]] = None
    ):
        try:
            await self._download_image(url, guild_id=guild_id)
            return True
        except TypeError:
            return False

    # uses k-means algorithm to find color from bg, rank is abundance of color, descending
    async def _auto_color(self, ctx, url: str, ranks):
        phrases = ["Calculating colors..."]  # in case I want more
        await ctx.send("{}".format(random.choice(phrases)))
        clusters = 10

        try:
            image = await self._download_image(url, guild_id=ctx.guild.id)
        except TypeError:
            raise

        im = Image.open(image).convert("RGBA")
        im = im.resize((290, 290))  # resized to reduce time
        ar = numpy.asarray(im)
        shape = ar.shape
        ar = ar.reshape(numpy.product(shape[:2]), shape[2])

        codes, dist = cluster.vq.kmeans(ar.astype(float), clusters)
        vecs, dist = cluster.vq.vq(ar, codes)  # assign codes
        counts, bins = numpy.histogram(vecs, len(codes))  # count occurrences

        # sort counts
        freq_index = []
        index = 0
        for count in counts:
            freq_index.append((index, count))
            index += 1
        sorted_list = sorted(freq_index, key=operator.itemgetter(1), reverse=True)

        colors = []
        for rank in ranks:
            color_index = min(rank, len(codes))
            peak = codes[sorted_list[color_index][0]]  # gets the original index
            peak = peak.astype(int)

            colors.append("".join(format(c, "02x") for c in peak))
        image.close()
        im.close()
        return colors  # returns array

    # changes large numbers into smaller strings, ie "10000" becomes 10k
    # https://github.com/gabzin/django-ytdownloader/blob/e59e728aeac459b73fd4fb9ca663560855af19fd/YouTubeDownloader/views.py#L25
    def _humanize_number(self, number):
        if not number:
            return 0
        negative = "-" if number < 0 else ""
        if number < 0:
            number *= -1

        units = ["", "K", "M", "B", "T", "Q"]
        k = 1000.0
        magnitude = int(floor(log(number, k)))
        if magnitude >= len(units):
            return f">999{units[-1]}"
        return f"{negative}{number / k**magnitude:.0f}{units[magnitude]}"

    # finds the the pixel to center the text
    def _center(self, start, end, text, font):
        dist = end - start
        width = self._get_character_pixel_width(font, text)
        start_pos = start + ((dist - width) / 2)
        return int(start_pos)

    def char_in_font(self, unicode_char, font):
        for cmap in font["cmap"].tables:
            if cmap.isUnicode():
                if ord(unicode_char) in cmap.cmap:
                    return True
        return False

    def _contrast(self, bg_color, color1, color2):
        """returns color that contrasts better in background"""
        color1_ratio = self._contrast_ratio(bg_color, color1)
        color2_ratio = self._contrast_ratio(bg_color, color2)
        if color1_ratio >= color2_ratio:
            return color1
        return color2

    def _luminance(self, color):
        # convert to greyscale
        luminance = float((0.2126 * color[0]) + (0.7152 * color[1]) + (0.0722 * color[2]))
        return luminance

    def _contrast_ratio(self, bgcolor, foreground):
        f_lum = float(self._luminance(foreground) + 0.05)
        bg_lum = float(self._luminance(bgcolor) + 0.05)

        if bg_lum > f_lum:
            return bg_lum / f_lum
        return f_lum / bg_lum

    def _name(self, user, max_length):
        """returns a string with possibly a nickname"""
        if user.name == user.display_name:
            return user.name
        return "{} ({})".format(
            user.name,
            self._truncate_text(user.display_name, max_length - len(user.name) - 3),
        )

    def _add_corners(self, im, rad, multiplier=6):
        raw_length = rad * 2 * multiplier
        circle = Image.new("L", (raw_length, raw_length), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, raw_length, raw_length), fill=255)
        circle = circle.resize((rad * 2, rad * 2), LANCZOS)

        alpha = Image.new("L", im.size, 255)
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        circle.close()
        alpha.close()
        return im
