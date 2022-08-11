from copy import copy
from typing import Any, Dict

from redbot.core import Config
from redbot.core.utils import AsyncIter

from .utils import get_config, get_log

logs = get_log()


async def run_migration():
    config = get_config()

    logs.debug("Checking migration status...")
    actual_migration = await config.migration()
    logs.info(f"Migration #{actual_migration} detected, running migrations if required.")

    # Migration 1 (1.0.2 -> 2.0.0)
    if actual_migration == 0:
        logs.warning("Running migration #1...")
        await migration_1(config)
        logs.warning("Migration #1 has been completed.")


async def migration_1(config: Config):
    keys_transformation: Dict[str, str] = {
        "logschannel": "logs_channel",
        "autoroles": "auto_roles",
        "temprole": "temp_role",
    }
    defaults_values: Dict[str, Any] = {
        "logschannel": None,
        "autoroles": [],
        "temprole": None,
    }

    guilds_data = await config.all_guilds()
    async for guild_id, data in AsyncIter(guilds_data.items()):
        guild_id: int
        data: Dict[str, Any]
        new_values = copy(data)

        for old_key, new_key in keys_transformation.items():
            new_values[new_key] = data.get(old_key, defaults_values[old_key])
            if old_key in new_values:
                del new_values[old_key]

        if data.get("type") == "plain":
            new_values["type"] = "text"

        logs.debug(f"Modified data for guild with ID {guild_id}:\nOld: {data}\nNew: {new_values}")

        await config.guild_from_id(guild_id).set_raw(value=new_values)
        for key in keys_transformation:
            await config.guild_from_id(guild_id).clear_raw(key)

    await config.migration.set("1")
