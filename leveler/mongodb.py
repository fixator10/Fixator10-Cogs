from .abc import MixinMeta

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import errors as mongoerrors
except Exception as e:
    raise RuntimeError(f"Can't load pymongo/motor:{e}\nInstall 'pymongo' and 'motor' packages")


REQUIRED_MONGODB_VERSION = [4, 4]


class MongoDBUnsupportedVersion(Exception):
    def __init__(self, version, current_version):
        super().__init__(
            "MongoDB connection succeeded, but Leveler requires "
            f"version {'.'.join(version)}, and you have {current_version}.\n"
            "Please follow MongoDB docs for upgrade."
        )


class MongoDB(MixinMeta):
    """MongoDB connection handling"""

    async def _connect_to_mongo(self):
        self.log.info("Connecting to MongoDB...")
        if self._db_ready:
            self._db_ready = False
        self._disconnect_mongo()
        config = await self.config.custom("MONGODB").all()
        try:
            self.client = AsyncIOMotorClient(**{k: v for k, v in config.items() if k != "db_name"})
            info = await self.client.server_info()
            if not info.get("versionArray", []) > REQUIRED_MONGODB_VERSION:
                self.client.close()
                raise MongoDBUnsupportedVersion(REQUIRED_MONGODB_VERSION, info.get("version", "?"))
            self.db = self.client[config["db_name"]]
            self._db_ready = True
            self.log.info("MongoDB: connection established.")
        except (
            mongoerrors.ServerSelectionTimeoutError,
            mongoerrors.ConfigurationError,
            mongoerrors.OperationFailure,
            MongoDBUnsupportedVersion,
        ) as error:
            self.log.exception(
                "Can't connect to the MongoDB server.\nFollow instructions on Git/online to install MongoDB.",
                exc_info=error,
            )
            self.client = None
            self.db = None
        return self.client

    def _disconnect_mongo(self):
        if self.client:
            self.client.close()

    # handles user creation, adding new server, blocking
    async def _create_user(self, user, server):
        if not self._db_ready:
            return
        if user.bot:
            return
        async with self._db_lock:
            self.log.debug("Locking db for user %s creation", user)
            try:
                userinfo = await self.db.users.find_one({"user_id": str(user.id)})
                backgrounds = await self.config.backgrounds()
                if not userinfo:
                    new_account = {
                        "user_id": str(user.id),
                        "username": user.name,
                        "servers": {},
                        "total_exp": 0,
                        "profile_background": backgrounds["profile"]["default"],
                        "rank_background": backgrounds["rank"]["default"],
                        "levelup_background": backgrounds["levelup"]["default"],
                        "title": "",
                        "info": "I am a mysterious person.",
                        "rep": 0,
                        "badges": {},
                        "active_badges": {},
                        "rep_color": [],
                        "badge_col_color": [],
                        "rep_block": 0,
                        "chat_block": 0,
                        "lastrep": 0,
                        "last_message": "",
                    }
                    await self.db.users.insert_one(new_account)

                userinfo = await self.db.users.find_one({"user_id": str(user.id)})

                if "username" not in userinfo or userinfo["username"] != user.name:
                    await self.db.users.update_one(
                        {"user_id": str(user.id)},
                        {"$set": {"username": user.name}},
                        upsert=True,
                    )

                if server and (
                    "servers" not in userinfo or str(server.id) not in userinfo["servers"]
                ):
                    await self.db.users.update_one(
                        {"user_id": str(user.id)},
                        {
                            "$set": {
                                "servers.{}.level".format(server.id): 0,
                                "servers.{}.current_exp".format(server.id): 0,
                            }
                        },
                        upsert=True,
                    )
            except AttributeError as error:
                self.log.error(f"Unable to create/update user {user.id}.", exc_info=error)
            self.log.debug("Unlocking db after user %s creation", user)
