import operator
import random
from io import BytesIO

from redbot.core.errors import CogLoadError

from .abc import MixinMeta

try:
    from PIL import Image, ImageDraw, ImageFilter
except Exception as e:
    raise CogLoadError(f"Can't load pillow: {e}\nDo '[p]pipinstall pillow'.")


try:
    import numpy
    from scipy import cluster
except Exception as e:
    print(
        f"{__file__}: numpy/scipy is unable to import: {e}\nAutocolor feature will be unavailable"
    )


class DefaultImageGeneratorsUtils(MixinMeta):
    """Utils for default image generators"""

    async def _valid_image_url(self, url):
        try:
            async with self.session.get(url) as r:
                image = await r.content.read()
            image = BytesIO(image)
            Image.open(image).convert("RGBA")
            return True
        except IOError:
            return False

    # uses k-means algorithm to find color from bg, rank is abundance of color, descending
    async def _auto_color(self, ctx, url: str, ranks):
        phrases = ["Calculating colors..."]  # in case I want more
        await ctx.send("**{}**".format(random.choice(phrases)))
        clusters = 10

        async with self.session.get(url) as r:
            image = await r.content.read()
        image = BytesIO(image)

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
        return colors  # returns array

    # finds the the pixel to center the text
    async def _center(self, start, end, text, font):
        dist = end - start
        width = font.getsize(text)[0]
        start_pos = start + ((dist - width) / 2)
        return int(start_pos)

    async def char_in_font(self, unicode_char, font):
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

    async def _name(self, user, max_length):
        """returns a string with possibly a nickname"""
        if user.name == user.display_name:
            return user.name
        return "{} ({})".format(
            user.name,
            await self._truncate_text(user.display_name, max_length - len(user.name) - 3),
            max_length,
        )

    async def _add_dropshadow(
        self,
        image,
        offset=(4, 4),
        background=0x000,
        shadow=0x0F0,
        border=3,
        iterations=5,
    ):
        total_width = image.size[0] + abs(offset[0]) + 2 * border
        total_height = image.size[1] + abs(offset[1]) + 2 * border
        back = Image.new(image.mode, (total_width, total_height), background)

        # Place the shadow, taking into account the offset from the image
        shadow_left = border + max(offset[0], 0)
        shadow_top = border + max(offset[1], 0)
        back.paste(
            shadow,
            [
                shadow_left,
                shadow_top,
                shadow_left + image.size[0],
                shadow_top + image.size[1],
            ],
        )

        n = 0
        while n < iterations:
            back = back.filter(ImageFilter.BLUR)
            n += 1

        # Paste the input image onto the shadow backdrop
        image_left = border - min(offset[0], 0)
        image_top = border - min(offset[1], 0)
        back.paste(image, (image_left, image_top))
        return back

    async def _add_corners(self, im, rad, multiplier=6):
        raw_length = rad * 2 * multiplier
        circle = Image.new("L", (raw_length, raw_length), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, raw_length, raw_length), fill=255)
        circle = circle.resize((rad * 2, rad * 2), Image.ANTIALIAS)

        alpha = Image.new("L", im.size, 255)
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im
