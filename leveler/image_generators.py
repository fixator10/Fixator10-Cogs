import operator
import textwrap
from io import BytesIO
from logging import getLogger

import discord
from fontTools.ttLib import TTFont
from redbot.core import bank
from redbot.core.data_manager import bundled_data_path
from redbot.core.errors import CogLoadError
from redbot.core.utils import AsyncIter

from .abc import MixinMeta

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
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


log = getLogger("red.fixator10-cogs.leveler")


AVATAR_FORMAT = "webp" if pil_features.check("webp_anim") else "jpg"
log.debug(f"using {AVATAR_FORMAT} avatar format")


class ImageGenerators(MixinMeta):
    """Image generators"""

    def make_rank_image(
        self,
        rank_background,
        rank_avatar,
        user,
        server,
        userinfo,
        exp_total,
        server_rank,
        bank_credits,
        credits_name,
    ):
        # fonts
        font_thin_file = f"{bundled_data_path(self)}/Uni_Sans_Thin.ttf"
        font_heavy_file = f"{bundled_data_path(self)}/Uni_Sans_Heavy.ttf"
        font_bold_file = f"{bundled_data_path(self)}/SourceSansPro-Semibold.ttf"
        font_unicode_file = f"{bundled_data_path(self)}/unicode.ttf"

        name_fnt = ImageFont.truetype(font_heavy_file, 24)
        name_u_fnt = ImageFont.truetype(font_unicode_file, 24)
        label_fnt = ImageFont.truetype(font_bold_file, 16)
        exp_fnt = ImageFont.truetype(font_bold_file, 9)
        large_fnt = ImageFont.truetype(font_thin_file, 24)
        symbol_u_fnt = ImageFont.truetype(font_unicode_file, 15)

        bg_image_original = Image.open(rank_background)
        bg_image = bg_image_original.convert("RGBA")
        bg_image_original.close()
        profile_image_original = Image.open(rank_avatar)
        profile_image = profile_image_original.convert("RGBA")
        profile_image_original.close()
        rank_background.close()
        rank_avatar.close()

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x
            check_font = TTFont(font.path)

            for char in text:
                # if char.isalnum() or char in string.punctuation or char in string.whitespace:
                if self.char_in_font(char, check_font):
                    draw.text((write_pos, y), "{}".format(char), font=font, fill=fill)
                    write_pos += self._get_character_pixel_width(font, char)
                else:
                    draw.text((write_pos, y), "{}".format(char), font=unicode_font, fill=fill)
                    write_pos += self._get_character_pixel_width(unicode_font, char)
            check_font.close()

        # set canvas
        width = 390
        height = 100
        bg_color = (255, 255, 255, 0)
        bg_width = width - 50
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(process)

        # info section
        info_section = Image.new("RGBA", (bg_width, height), bg_color)
        info_section_process = Image.new("RGBA", (bg_width, height), bg_color)
        # puts in background
        temp = bg_image
        bg_image = bg_image.resize((width, height), LANCZOS)
        temp.close()
        temp = bg_image
        bg_image = bg_image.crop((0, 0, width, height))
        temp.close()
        info_section.paste(bg_image, (0, 0))

        # draw transparent overlays
        draw_overlay = ImageDraw.Draw(info_section_process)
        draw_overlay.rectangle([(0, 0), (bg_width, 20)], fill=(230, 230, 230, 200))
        draw_overlay.rectangle([(0, 20), (bg_width, 30)], fill=(120, 120, 120, 180))  # Level bar
        exp_frac = int(userinfo["servers"][str(server.id)]["current_exp"])
        exp_width = int(bg_width * (exp_frac / exp_total))
        if "rank_info_color" in userinfo.keys():
            exp_color = tuple(userinfo["rank_info_color"])
            exp_color = (
                exp_color[0],
                exp_color[1],
                exp_color[2],
                180,
            )  # increase transparency
        else:
            exp_color = (140, 140, 140, 230)
        draw_overlay.rectangle([(0, 20), (exp_width, 30)], fill=exp_color)  # Exp bar
        draw_overlay.rectangle([(0, 30), (bg_width, 31)], fill=(0, 0, 0, 255))  # Divider
        # draw_overlay.rectangle([(0,35), (bg_width,100)], fill=(230,230,230,0)) # title overlay
        for i in range(0, 70):
            draw_overlay.rectangle(
                [(0, height - i), (bg_width, height - i)],
                fill=(20, 20, 20, 255 - i * 3),
            )  # title overlay

        # draw corners and finalize
        info_section = Image.alpha_composite(info_section, info_section_process)
        info_section = self._add_corners(info_section, 25)
        process.paste(info_section, (35, 0))

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 100
        circle_left = 0
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # drawing level border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(250, 250, 250, 250))
        # put on profile circle background
        temp = lvl_circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), LANCZOS)
        temp.close()
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), LANCZOS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)
        lvl_bar_mask.close()

        # draws mask
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        temp = output
        output.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        temp = mask
        mask = mask.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        temp = profile_image
        profile_image = profile_image.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # draw text
        grey_color = (100, 100, 100, 255)
        white_color = (220, 220, 220, 255)

        # name
        _write_unicode(
            self._truncate_text(self._name(user, 20), 20),
            100,
            0,
            name_fnt,
            name_u_fnt,
            grey_color,
        )  # Name

        balance_width = 63

        # labels
        v_label_align = 75
        info_text_color = white_color
        credits_name = (
            credits_name.upper()
            if label_fnt.getmask(credits_name.upper()).getbbox()[2] <= balance_width
            else "BALANCE"
        )

        draw.text(
            (self._center(100, 200, "  RANK", label_fnt), v_label_align),
            "  RANK",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(100, 360, "  LEVEL", label_fnt), v_label_align),
            "  LEVEL",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(260, 360, credits_name, label_fnt), v_label_align),
            credits_name,
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        local_symbol = "\N{HOUSE BUILDING} "
        _write_unicode(
            local_symbol,
            117,
            v_label_align + 4,
            label_fnt,
            symbol_u_fnt,
            info_text_color,
        )  # Symbol
        _write_unicode(
            local_symbol,
            195,
            v_label_align + 4,
            label_fnt,
            symbol_u_fnt,
            info_text_color,
        )  # Symbol

        # userinfo
        server_rank = "#{}".format(self._humanize_number(server_rank))
        draw.text(
            (self._center(100, 200, server_rank, large_fnt), v_label_align - 30),
            server_rank,
            font=large_fnt,
            fill=info_text_color,
        )  # Rank
        level_text = "{}".format(userinfo["servers"][str(server.id)]["level"])
        draw.text(
            (self._center(95, 360, level_text, large_fnt), v_label_align - 30),
            level_text,
            font=large_fnt,
            fill=info_text_color,
        )  # Level
        credit_txt = f"{self._humanize_number(bank_credits)}"
        draw.text(
            (self._center(260, 360, credit_txt, large_fnt), v_label_align - 30),
            credit_txt,
            font=large_fnt,
            fill=info_text_color,
        )  # Balance
        exp_text = f"{exp_frac}/{exp_total}"
        draw.text(
            (self._center(80, 360, exp_text, exp_fnt), 19),
            exp_text,
            font=exp_fnt,
            fill=info_text_color,
        )  # Rank

        result = Image.alpha_composite(result, process)
        file = BytesIO()
        result.save(file, "PNG", quality=100)
        profile_image.close()
        bg_image.close()
        process.close()
        info_section.close()
        info_section_process.close()
        mask.close()
        lvl_circle.close()
        result.close()
        file.seek(0)
        return file

    def make_levelup_image(
        self,
        level_background,
        level_avatar,
        userinfo,
        server,
    ):
        # fonts
        font_thin_file = f"{bundled_data_path(self)}/Uni_Sans_Thin.ttf"
        level_fnt = ImageFont.truetype(font_thin_file, 23)

        bg_image_original = Image.open(level_background)
        bg_image = bg_image_original.convert("RGBA")
        bg_image_original.close()
        profile_image_original = Image.open(level_avatar)
        profile_image = profile_image_original.convert("RGBA")
        profile_image_original.close()
        level_background.close()
        level_avatar.close()

        # set canvas
        width = 176
        height = 67
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(process)

        # puts in background
        temp = bg_image
        bg_image = bg_image.resize((width, height), LANCZOS)
        temp.close()
        temp = bg_image
        bg_image = bg_image.crop((0, 0, width, height))
        temp.close()
        result.paste(bg_image, (0, 0))

        # info section
        lvl_circle_dia = 60
        total_gap = 2
        border = int(total_gap / 2)
        info_section = Image.new("RGBA", (165, 55), (230, 230, 230, 20))
        info_section = self._add_corners(info_section, int(lvl_circle_dia / 2))
        process.paste(info_section, (border, border))

        # draw transparent overlay
        if "levelup_info_color" in userinfo.keys():
            info_color = tuple(userinfo["levelup_info_color"])
            info_color = (
                info_color[0],
                info_color[1],
                info_color[2],
                150,
            )  # increase transparency
        else:
            info_color = (30, 30, 30, 150)

        for i in range(0, height):
            draw.rectangle(
                [(0, height - i), (width, height - i)],
                fill=(info_color[0], info_color[1], info_color[2], 255 - i * 3),
            )  # title overlay

        # draw circle
        multiplier = 6
        circle_left = 4
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier
        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(250, 250, 250, 180))
        temp = lvl_circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), LANCZOS)
        temp.close()
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), LANCZOS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)
        lvl_bar_mask.close()

        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        temp = output
        output.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        temp = mask
        mask = mask.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        temp = profile_image
        profile_image = profile_image.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_text = (250, 250, 250, 255)
        dark_text = (35, 35, 35, 230)
        level_up_text = self._contrast(info_color, white_text, dark_text)
        lvl_text = "LEVEL {}".format(
            self._humanize_number(userinfo["servers"][str(server.id)]["level"])
        )
        draw.text(
            (self._center(60, 170, lvl_text, level_fnt), 23),
            lvl_text,
            font=level_fnt,
            fill=level_up_text,
        )  # Level Number

        result = Image.alpha_composite(result, process)
        result = self._add_corners(result, int(height / 2))
        file = BytesIO()
        result.save(file, "PNG", quality=100)
        profile_image.close()
        bg_image.close()
        lvl_circle.close()
        mask.close()
        info_section.close()
        process.close()
        result.close()
        file.seek(0)
        return file

    def make_profile_image(
        self,
        profile_background,
        profile_avatar,
        user,
        userinfo,
        global_rank,
        level,
        level_exp,
        next_level_exp,
        bank_credits,
        credits_name,
        sorted_badges,
        badges_images,
    ):
        font_thin_file = f"{bundled_data_path(self)}/Uni_Sans_Thin.ttf"
        font_heavy_file = f"{bundled_data_path(self)}/Uni_Sans_Heavy.ttf"
        font_file = f"{bundled_data_path(self)}/Ubuntu-R_0.ttf"
        font_bold_file = f"{bundled_data_path(self)}/Ubuntu-B_0.ttf"
        font_unicode_file = f"{bundled_data_path(self)}/unicode.ttf"

        name_fnt = ImageFont.truetype(font_heavy_file, 30)
        name_u_fnt = ImageFont.truetype(font_unicode_file, 30)
        title_fnt = ImageFont.truetype(font_heavy_file, 22)
        title_u_fnt = ImageFont.truetype(font_unicode_file, 23)
        label_fnt = ImageFont.truetype(font_bold_file, 18)
        exp_fnt = ImageFont.truetype(font_bold_file, 13)
        large_fnt = ImageFont.truetype(font_thin_file, 33)
        rep_fnt = ImageFont.truetype(font_heavy_file, 26)
        rep_u_fnt = ImageFont.truetype(font_unicode_file, 30)
        text_fnt = ImageFont.truetype(font_file, 14)
        text_u_fnt = ImageFont.truetype(font_unicode_file, 14)
        symbol_u_fnt = ImageFont.truetype(font_unicode_file, 15)

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x
            check_font = TTFont(font.path)

            for char in text:
                # if char.isalnum() or char in string.punctuation or char in string.whitespace:
                if self.char_in_font(char, check_font):
                    draw.text((write_pos, y), "{}".format(char), font=font, fill=fill)
                    write_pos += self._get_character_pixel_width(font, char)
                else:
                    draw.text((write_pos, y), "{}".format(char), font=unicode_font, fill=fill)
                    write_pos += self._get_character_pixel_width(unicode_font, char)
            check_font.close()

        # COLORS
        white_color = (240, 240, 240, 255)
        if "rep_color" not in userinfo.keys() or not userinfo["rep_color"]:
            rep_fill = (92, 130, 203, 230)
        else:
            rep_fill = tuple(userinfo["rep_color"])
        # determines badge section color, should be behind the titlebar
        if "badge_col_color" not in userinfo.keys() or not userinfo["badge_col_color"]:
            badge_fill = (128, 151, 165, 230)
        else:
            badge_fill = tuple(userinfo["badge_col_color"])
        if "profile_info_color" in userinfo.keys():
            info_fill = tuple(userinfo["profile_info_color"])
        else:
            info_fill = (30, 30, 30, 220)
        info_fill_tx = (info_fill[0], info_fill[1], info_fill[2], 150)
        if "profile_exp_color" not in userinfo.keys() or not userinfo["profile_exp_color"]:
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["profile_exp_color"])
        if badge_fill == (128, 151, 165, 230):
            level_fill = white_color
        else:
            level_fill = self._contrast(exp_fill, rep_fill, badge_fill)

        bg_image_original = Image.open(profile_background)
        bg_image = bg_image_original.convert("RGBA")
        bg_image_original.close()
        profile_image_original = Image.open(profile_avatar)
        profile_image = profile_image_original.convert("RGBA")
        profile_image_original.close()
        profile_background.close()
        profile_avatar.close()

        # set canvas
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (340, 390), bg_color)
        process = Image.new("RGBA", (340, 390), bg_color)

        # draw
        draw = ImageDraw.Draw(process)

        # puts in background
        temp = bg_image
        bg_image = bg_image.resize((340, 340), LANCZOS)
        temp.close()
        temp = bg_image
        bg_image = bg_image.crop((0, 0, 340, 305))
        temp.close()
        result.paste(bg_image, (0, 0))

        # draw filter
        draw.rectangle([(0, 0), (340, 340)], fill=(0, 0, 0, 10))

        draw.rectangle([(0, 134), (340, 325)], fill=info_fill_tx)  # general content
        # draw profile circle
        multiplier = 8
        lvl_circle_dia = 116
        circle_left = 14
        circle_top = 48
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # border
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse(
            [0, 0, raw_length, raw_length],
            fill=(255, 255, 255, 255),
            outline=(255, 255, 255, 250),
        )
        # put border
        temp = lvl_circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), LANCZOS)
        temp.close()
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), LANCZOS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)
        lvl_bar_mask.close()

        # put in profile picture
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        temp = mask
        mask = mask.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        temp = profile_image
        profile_image = profile_image.resize((profile_size, profile_size), LANCZOS)
        temp.close()
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_color = (240, 240, 240, 255)
        light_color = (160, 160, 160, 255)
        dark_color = (35, 35, 35, 255)

        head_align = 140
        # determine info text color
        info_text_color = self._contrast(info_fill, white_color, dark_color)
        _write_unicode(
            (self._truncate_text(user.name, 22)).upper(),
            head_align,
            142,
            name_fnt,
            name_u_fnt,
            info_text_color,
        )  # NAME
        _write_unicode(
            userinfo["title"].upper(),
            head_align,
            170,
            title_fnt,
            title_u_fnt,
            info_text_color,
        )

        # draw divider
        draw.rectangle([(0, 323), (340, 324)], fill=(0, 0, 0, 255))  # box
        # draw text box
        draw.rectangle(
            [(0, 324), (340, 390)], fill=(info_fill[0], info_fill[1], info_fill[2], 255)
        )  # box

        # rep_text = "{} REP".format(userinfo["rep"])
        rep_text = "{}".format(self._humanize_number(userinfo["rep"]))
        _write_unicode("\N{HEAVY BLACK HEART}", 257, 9, rep_fnt, rep_u_fnt, rep_fill)
        draw.text(
            (self._center(278, 340, rep_text, rep_fnt), 10),
            rep_text,
            font=rep_fnt,
            fill=rep_fill,
        )  # Exp Text

        balance_width = 85

        credits_name = (
            credits_name.upper()
            if label_fnt.getmask(credits_name.upper()).getbbox()[2] <= balance_width
            else "BALANCE"
        )

        label_align = 362  # vertical
        draw.text(
            (self._center(0, 140, "    RANK", label_fnt), label_align),
            "    RANK",
            font=label_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(0, 340, "    LEVEL", label_fnt), label_align),
            "    LEVEL",
            font=label_fnt,
            fill=info_text_color,
        )  # Exp
        draw.text(
            (self._center(200, 340, credits_name, label_fnt), label_align),
            credits_name,
            font=label_fnt,
            fill=info_text_color,
        )  # Credits

        global_symbol = "\N{EARTH GLOBE AMERICAS} "

        _write_unicode(
            global_symbol, 36, label_align + 5, label_fnt, symbol_u_fnt, info_text_color
        )  # Symbol
        _write_unicode(
            global_symbol,
            134,
            label_align + 5,
            label_fnt,
            symbol_u_fnt,
            info_text_color,
        )  # Symbol

        # userinfo
        global_rank = "#{}".format(self._humanize_number(global_rank))
        global_level = "{}".format(level)
        draw.text(
            (self._center(0, 140, global_rank, large_fnt), label_align - 27),
            global_rank,
            font=large_fnt,
            fill=info_text_color,
        )  # Rank
        draw.text(
            (self._center(0, 340, global_level, large_fnt), label_align - 27),
            global_level,
            font=large_fnt,
            fill=info_text_color,
        )  # Exp
        # draw level bar
        exp_font_color = self._contrast(exp_fill, light_color, dark_color)
        exp_frac = int(userinfo["total_exp"] - level_exp)
        bar_length = int(340 * (exp_frac / next_level_exp))
        # fix10: idk what im doing here, if you understand something, pls help
        draw.rectangle(
            [(0, 305), (340, 323)],
            fill=(level_fill[0], level_fill[1], level_fill[2], 245),
        )  # level box
        draw.rectangle(
            [(0, 305), (bar_length, 323)],
            fill=(exp_fill[0], exp_fill[1], exp_fill[2], 255),
        )  # box
        exp_text = f"{exp_frac}/{next_level_exp}"  # Exp
        draw.text(
            (self._center(0, 340, exp_text, exp_fnt), 305),
            exp_text,
            font=exp_fnt,
            fill=exp_font_color,
        )  # Exp Text

        credit_txt = f"{self._humanize_number(bank_credits)}"
        draw.text(
            (self._center(200, 340, credit_txt, large_fnt), label_align - 27),
            credit_txt,
            font=large_fnt,
            fill=info_text_color,
        )  # Credits

        if not userinfo["title"]:
            offset = 170
        else:
            offset = 195
        margin = 140
        txt_color = self._contrast(info_fill, white_color, dark_color)
        for line in textwrap.wrap(userinfo["info"], width=27):
            # for line in textwrap.wrap('userinfo["info"]', width=200):
            # draw.text((margin, offset), line, font=text_fnt, fill=white_color)
            _write_unicode(line, margin, offset, text_fnt, text_u_fnt, txt_color)
            offset += 18

        # if await self.config.badge_type() == "circles":
        # circles require antialiasing
        vert_pos = 172
        right_shift = 0
        left = 9 + right_shift
        size = 38
        total_gap = 4  # /2
        hor_gap = 6
        vert_gap = 6
        border_width = int(total_gap / 2)
        multiplier = 6  # for antialiasing
        raw_length = size * multiplier
        mult = [
            (0, 0),
            (1, 0),
            (2, 0),
            (0, 1),
            (1, 1),
            (2, 1),
            (0, 2),
            (1, 2),
            (2, 2),
        ]
        for num in range(9):
            coord = (
                left + int(mult[num][0]) * int(hor_gap + size),
                vert_pos + int(mult[num][1]) * int(vert_gap + size),
            )
            # draw mask circle
            mask = Image.new("L", (raw_length, raw_length), 0)
            draw_thumb = ImageDraw.Draw(mask)
            draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)
            if num < len(sorted_badges[:9]) and badges_images[num]:
                pair = sorted_badges[num]
                badge = pair[0]
                border_color = badge["border_color"]

                badge_image_original = Image.open(badges_images[num])
                badge_image = badge_image_original.convert("RGBA")
                badges_images[num].close()
                badge_image_original.close()
                badge_image_resized = badge_image.resize((raw_length, raw_length), LANCZOS)
                badge_image.close()

                # structured like this because if border = 0, still leaves outline.
                if border_color:
                    square = Image.new("RGBA", (raw_length, raw_length), border_color)
                    # put border on ellipse/circle
                    output = ImageOps.fit(square, (raw_length, raw_length), centering=(0.5, 0.5))
                    temp = output
                    output = output.resize((size, size), LANCZOS)
                    temp.close()
                    outer_mask = mask.resize((size, size), LANCZOS)
                    process.paste(output, coord, outer_mask)
                    outer_mask.close()

                    # put on ellipse/circle
                    output = ImageOps.fit(
                        badge_image_resized,
                        (raw_length, raw_length),
                        centering=(0.5, 0.5),
                    )
                    temp = output
                    output = output.resize((size - total_gap, size - total_gap), LANCZOS)
                    temp.close()
                    inner_mask = mask.resize((size - total_gap, size - total_gap), LANCZOS)
                    process.paste(
                        output,
                        (coord[0] + border_width, coord[1] + border_width),
                        inner_mask,
                    )
                    inner_mask.close()
                    square.close()
                else:
                    # put on ellipse/circle
                    output = ImageOps.fit(
                        badge_image_resized,
                        (raw_length, raw_length),
                        centering=(0.5, 0.5),
                    )
                    temp = output
                    output = output.resize((size, size), LANCZOS)
                    temp.close()
                    outer_mask = mask.resize((size, size), LANCZOS)
                    process.paste(output, coord, outer_mask)
                    outer_mask.close()
                badge_image_resized.close()
            else:
                plus_fill = exp_fill
                # put on ellipse/circle
                plus_square = Image.new("RGBA", (raw_length, raw_length))
                plus_draw = ImageDraw.Draw(plus_square)
                plus_draw.rectangle(
                    [(0, 0), (raw_length, raw_length)],
                    fill=(info_fill[0], info_fill[1], info_fill[2], 245),
                )
                # draw plus signs
                margin = 60
                thickness = 40
                v_left = int(raw_length / 2 - thickness / 2)
                v_right = v_left + thickness
                v_top = margin
                v_bottom = raw_length - margin
                plus_draw.rectangle(
                    [(v_left, v_top), (v_right, v_bottom)],
                    fill=(plus_fill[0], plus_fill[1], plus_fill[2], 245),
                )
                h_left = margin
                h_right = raw_length - margin
                h_top = int(raw_length / 2 - thickness / 2)
                h_bottom = h_top + thickness
                plus_draw.rectangle(
                    [(h_left, h_top), (h_right, h_bottom)],
                    fill=(plus_fill[0], plus_fill[1], plus_fill[2], 245),
                )
                # put border on ellipse/circle
                output = ImageOps.fit(plus_square, (raw_length, raw_length), centering=(0.5, 0.5))
                temp = output
                output = output.resize((size, size), LANCZOS)
                temp.close()
                outer_mask = mask.resize((size, size), LANCZOS)
                process.paste(output, coord, outer_mask)
                outer_mask.close()
                plus_square.close()
            mask.close()

        result = Image.alpha_composite(result, process)
        result = self._add_corners(result, 25)
        file = BytesIO()
        result.save(file, "PNG", quality=100)
        profile_image.close()
        bg_image.close()
        lvl_circle.close()
        mask.close()
        process.close()
        result.close()
        file.seek(0)
        return file

    async def draw_rank(self, user, server):
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        # get urls
        bg_url = userinfo["rank_background"]
        try:
            rank_background = await self._download_image(bg_url)
        except TypeError:
            raise
        rank_avatar = BytesIO()
        try:
            await user.display_avatar.replace(format=AVATAR_FORMAT).save(rank_avatar)
        except discord.HTTPException:
            rank_avatar = f"{bundled_data_path(self)}/defaultavatar.png"

        file = await self.asyncify_thread(
            self.make_rank_image,
            rank_background,
            rank_avatar,
            user,
            server,
            userinfo,
            await self._required_exp(userinfo["servers"][str(server.id)]["level"]),
            await self._find_server_rank(user, server),
            await bank.get_balance(user),
            await bank.get_currency_name(server),
        )
        return file

    async def draw_levelup(self, user, server):
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        # get urls
        bg_url = userinfo["levelup_background"]
        try:
            level_background = await self._download_image(bg_url)
        except TypeError:
            raise
        level_avatar = BytesIO()
        try:
            await user.display_avatar.replace(format=AVATAR_FORMAT).save(level_avatar)
        except discord.HTTPException:
            level_avatar = f"{bundled_data_path(self)}/defaultavatar.png"

        file = await self.asyncify_thread(
            self.make_levelup_image, level_background, level_avatar, userinfo, server
        )
        return file

    async def draw_profile(self, user, server):
        # get urls
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)
        bg_url = userinfo["profile_background"]

        profile_background = await self._download_image(bg_url)
        profile_avatar = BytesIO()
        try:
            await user.display_avatar.replace(format=AVATAR_FORMAT).save(profile_avatar)
        except discord.HTTPException:
            profile_avatar.close()
            profile_avatar = f"{bundled_data_path(self)}/defaultavatar.png"

        level = await self._find_level(userinfo["total_exp"])

        priority_badges = []
        async for badgename in AsyncIter(userinfo["badges"].keys()):
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != 0 and priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = await self.asyncify(
            sorted, priority_badges, key=operator.itemgetter(1), reverse=True
        )

        badges_images = []
        async for badge in AsyncIter(sorted_badges[:9]):
            bg_color = badge[0]["bg_img"]
            try:
                bg_image = await self._download_image(bg_color, guild_id=server.id)
                badges_images.append(bg_image)
            except TypeError:
                badges_images.append(None)

        file = await self.asyncify_thread(
            self.make_profile_image,
            profile_background,
            profile_avatar,
            user,
            userinfo,
            await self._find_global_rank(user),
            level,
            await self._level_exp(level),
            await self._required_exp(level),
            await bank.get_balance(user),
            await bank.get_currency_name(server),
            sorted_badges,
            badges_images,
        )
        return file
