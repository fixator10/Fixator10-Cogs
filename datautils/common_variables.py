import string

import discord

NON_ESCAPABLE_CHARACTERS = string.ascii_letters + string.digits
TWEMOJI_URL = "https://twemoji.maxcdn.com/v/latest/72x72"
APP_ICON_URL = "https://cdn.discordapp.com/app-icons/{app_id}/{icon_hash}.png"

_ = lambda s: s

GUILD_FEATURES = {
    "VIP_REGIONS": _("384kbps voice bitrate"),
    "VANITY_URL": _("Vanity invite URL"),
    "INVITE_SPLASH": _("Invite splash{splash}"),
    "VERIFIED": _("Verified"),
    "PARTNERED": _("Discord Partner"),
    "MORE_EMOJI": _("Extended emoji limit"),  # Non-boosted?
    "DISCOVERABLE": _("Shows in Server Discovery{discovery}"),
    "FEATURABLE": _('Can be in "Featured" section of Server Discovery'),
    "COMMERCE": _("Store channels"),
    "NEWS": _("News channels"),
    "BANNER": _("Banner{banner}"),
    "ANIMATED_ICON": _("Animated icon"),
    "WELCOME_SCREEN_ENABLED": _("Welcome screen"),
    "PUBLIC_DISABLED": _("Cannot be public"),
    "ENABLED_DISCOVERABLE_BEFORE": _("Was in Server Discovery"),
    "COMMUNITY": _("Community server"),
    "TICKETED_EVENTS_ENABLED": _("Ticketed events"),
    "MONETIZATION_ENABLED": _("Monetization"),
    "MORE_STICKERS": _("Extended custom sticker slots"),
    "THREADS_ENABLED": _("Threads"),
    "THREADS_ENABLED_TESTING": _("Threads (testing)"),
    "PRIVATE_THREADS": _("Private threads"),  # "keep Discord’s core features free"
    "THREE_DAY_THREAD_ARCHIVE": _("3 day thread archive"),
    "SEVEN_DAY_THREAD_ARCHIVE": _("7 day thread archive"),
    "NEW_THREAD_PERMISSIONS": _("Enabled new thread permissions"),
    "ROLE_ICONS": _("Role icons"),
    "DISCOVERABLE_DISABLED": _("Cannot be in Server Discovery"),
    # Docs from https://github.com/vDelite/DiscordLists:
    "PREVIEW_ENABLED": _('Preview enabled ("Lurkable")'),
    "MEMBER_VERIFICATION_GATE_ENABLED": _("Member verification gate enabled"),
    "MEMBER_LIST_DISABLED": _("Member list disabled"),
    "PREMIUM_TIER_3_OVERRIDE": _("Permanent level 3 boost"),
    # im honestly idk what the fuck that shit means, and discord doesnt provides much docs,
    # so if you see that on your server while using my cog - idk what the fuck is that and how it got there,
    # ask discord to write fucking docs already
    "RELAY_ENABLED": _(
        "Shards connections to the guild to different nodes that relay information between each other."
    ),
    "FORCE_RELAY": _(
        "Shards connections to the guild to different nodes that relay information between each other."
    ),
}

ACTIVITY_TYPES = {
    discord.ActivityType.playing: _("Playing"),
    discord.ActivityType.watching: _("Watching"),
    discord.ActivityType.listening: _("Listening to"),
    discord.ActivityType.competing: _("Competing in"),
}

CHANNEL_TYPE_EMOJIS = {
    discord.ChannelType.text: "\N{SPEECH BALLOON}",
    discord.ChannelType.voice: "\N{SPEAKER}",
    discord.ChannelType.category: "\N{BOOKMARK TABS}",
    discord.ChannelType.news: "\N{NEWSPAPER}",
    discord.ChannelType.store: "\N{SHOPPING TROLLEY}",
    discord.ChannelType.private: "\N{BUST IN SILHOUETTE}",
    discord.ChannelType.group: "\N{BUSTS IN SILHOUETTE}",
    discord.ChannelType.stage_voice: "\N{SATELLITE ANTENNA}",
}

KNOWN_CHANNEL_TYPES = {
    "category": ("categories", _("Categories")),
    "text": ("text_channels", _("Text channels")),
    "voice": ("voice_channels", _("Voice channels")),
    "stage": ("stage_channels", _("Stage channels")),
}  # menu type: (guild attr name, i18n string)
