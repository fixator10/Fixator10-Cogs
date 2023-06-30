'use strict';

// behold, my beautiful code.
// also: behold the field where my fucks are grown, and thy shall see that it is barren.

angular.module('permissionsCalc', ['themes'])
    .config(['$locationProvider', function($locationProvider)
    {
        $locationProvider.html5Mode(true);
    }])
    .controller('calc', ['$scope', '$location', function($scope, $location)
    {
        let perms = parseInt($location.search().v);

        let generateScopes = function(scopes)
        {
            if (scopes === undefined)
                return 0;

            const map = {
                '' : 0x0, // sentinel
                'bot': 0x1,
                'connections': 0x2,
                'email': 0x4,
                'identify': 0x8,
                'guilds': 0x10,
                'guilds.join': 0x20,
                'gdm.join': 0x40,
                'messages.read': 0x80,
                'rpc': 0x100,
                'rpc.api': 0x200,
                'rpc.notifications.read': 0x400,
                'webhook.incoming': 0x800
            }

            return scopes.match(/(?:[\w.]+,?)/g).reduce((acc, val) => acc | map[val.replace(',','')], '');
        }

        $scope.generateInvite = function(provider, info, permissions)
        {
            if (info === undefined ||
                info.id === undefined ||
                permissions === undefined ||
                provider === undefined)
                return '';

            if (provider === 'discord')
            {
                if (!info.hasScope && info.hasCode)
                    return `https://discord.com/oauth2/authorize/?permissions=${permissions}&scope=bot&client_id=${info.id}&response_type=code`;
                else if(!info.hasScope)
                    return `https://discord.com/oauth2/authorize/?permissions=${permissions}&scope=bot&client_id=${info.id}`;
                else if (info.hasCode)
                    return `https://discord.com/oauth2/authorize/?permissions=${permissions}&scope=${info.scope}&client_id=${info.id}&response_type=code`;
                else
                    return `https://discord.com/oauth2/authorize/?permissions=${permissions}&scope=${info.scope}&client_id=${info.id}`;
            }
            else if (provider === 'embed')
            {
                if (!info.hasScope && info.hasCode)
                    return `https://discord.now.sh/${info.id}?p${permissions}&t1`;
                else if (!info.hasScope)
                    return `https://discord.now.sh/${info.id}?p${permissions}`;
                else if (info.hasCode)
                    return `https://discord.now.sh/${info.id}?p${permissions}&s${generateScopes(info.scope)}&t1`;
                else
                    return `https://discord.now.sh/${info.id}?p${permissions}&s${generateScopes(info.scope)}`;
            }
        }

        $scope.calculatePermissions = function()
        {
            let value = 0n;
            for (let sectionId in $scope.permissions)
            {
                let section = $scope.permissions[sectionId];
                for (let permissionId in section.permissions)
                {
                    let permission = section.permissions[permissionId];
                    if (permission.active)
                    {
                        value |= BigInt(permission.value);
                    }
                }
            }
            value = Number(value);
            $location.search('v', value);
            return value;
        }
        $scope.calculateExplanation = function()
        {
            let resultSects = [ ];
            for (let sectionId in $scope.permissions)
            {
                let section = $scope.permissions[sectionId];
                for (let permissionId in section.permissions)
                {
                    let permission = section.permissions[permissionId];
                    if (permission.active)
                    {
                        resultSects.push('0x'+permission.value.toString(16));
                    }
                }
            }
            if (resultSects.length == 0) { resultSects.push('0x0'); }
            return resultSects.join(' | ');
        }

        $scope.toggle = function(section)
        {
            for (let permissionId in section.permissions)
            {
                let permission = section.permissions[permissionId];
                if (permission.auto && section.active)
                    permission.active = true;
            }
        }

        $scope.disableActive = function(section)
        {
            section.active = false;
        }

        $scope.permissions = [
            {
                name: 'General',
                active: false,
                permissions: [
                    { active: false, id: 'administrator',                      name: 'Administrator',                      value: 0x8,           auto: false }, // 1 << 3
                    { active: false, id: 'view_audit_log',                     name: 'View Audit Log',                     value: 0x80,          auto: true  }, // 1 << 7
                    { active: false, id: 'manage_guild',                       name: 'Manage Server',                      value: 0x20,          auto: false }, // 1 << 5
                    { active: false, id: 'manage_roles',                       name: 'Manage Roles',                       value: 0x10000000,    auto: false }, // 1 << 28
                    { active: false, id: 'manage_channels',                    name: 'Manage Channels',                    value: 0x10,          auto: false }, // 1 << 4
                    { active: false, id: 'kick_members',                       name: 'Kick Members',                       value: 0x2,           auto: false }, // 1 << 1
                    { active: false, id: 'ban_members',                        name: 'Ban Members',                        value: 0x4,           auto: false }, // 1 << 2
                    { active: false, id: 'create_instant_invite',              name: 'Create Instant Invite',              value: 0x1,           auto: true  }, // 1 << 0
                    { active: false, id: 'change_nickname',                    name: 'Change Nickname',                    value: 0x4000000,     auto: true  }, // 1 << 26
                    { active: false, id: 'manage_nicknames',                   name: 'Manage Nicknames',                   value: 0x8000000,     auto: true  }, // 1 << 27
                    { active: false, id: 'manage_guild_expressions',           name: 'Manage Expressions',                 value: 0x40000000,    auto: false }, // 1 << 30
                    { active: false, id: 'create_guild_expressions',           name: 'Create Expressions',                 value: 0x80000000000, auto: true  }, // 1 << 43
                    { active: false, id: 'manage_webhooks',                    name: 'Manage Webhooks',                    value: 0x20000000,    auto: false }, // 1 << 29
                    { active: false, id: 'view_channel',                       name: 'Read Messages/View Channels',        value: 0x400,         auto: true  }, // 1 << 10
                    { active: false, id: 'manage_events',                      name: 'Manage Events',                      value: 0x200000000,   auto: true  }, // 1 << 33
                    { active: false, id: 'create_events',                      name: 'Create Events',                      value: 0x100000000000,auto: true  }, // 1 << 44
                    { active: false, id: 'moderate_members',                   name: 'Moderate Members',                   value: 0x10000000000, auto: false }, // 1 << 40
                    { active: false, id: 'view_guild_insights',                name: 'View Server Insights',               value: 0x80000,       auto: true  }, // 1 << 19
                    { active: false, id: 'view_creator_monetization_insights', name: 'View Creator Monetization Insights', value: 0x20000000000, auto: false }, // 1 << 41
                ]
            },
            {
                name: 'Text',
                active: false,
                permissions: [
                    { active: false, id: 'send_messages',            name: 'Send Messages',             value: 0x800,        auto: true  }, // 1 << 11
                    { active: false, id: 'create_public_threads',    name: 'Create Public Threads',     value: 0x800000000,  auto: true  }, // 1 << 35
                    { active: false, id: 'create_private_threads',   name: 'Create Private Threads',    value: 0x1000000000, auto: true  }, // 1 << 36
                    { active: false, id: 'send_messages_in_threads', name: 'Send Messages in Threads',  value: 0x4000000000, auto: true  }, // 1 << 38
                    { active: false, id: 'send_tts_messages',        name: 'Send TTS Messages',         value: 0x1000,       auto: true  }, // 1 << 12
                    { active: false, id: 'manage_messaes',           name: 'Manage Messages',           value: 0x2000,       auto: false }, // 1 << 13
                    { active: false, id: 'manage_threads',           name: 'Manage Threads',            value: 0x400000000,  auto: false }, // 1 << 34
                    { active: false, id: 'embed_links',              name: 'Embed Links',               value: 0x4000,       auto: true  }, // 1 << 14
                    { active: false, id: 'attach_files',             name: 'Attach Files',              value: 0x8000,       auto: true  }, // 1 << 15
                    { active: false, id: 'read_message_history',     name: 'Read Message History',      value: 0x10000,      auto: true  }, // 1 << 16
                    { active: false, id: 'mention_everyone',         name: 'Mention Everyone',          value: 0x20000,      auto: true  }, // 1 << 17
                    { active: false, id: 'use_external_emojis',      name: 'Use External Emojis',       value: 0x40000,      auto: true  }, // 1 << 18
                    { active: false, id: 'use_external_stickers',    name: 'Use External Stickers',     value: 0x2000000000, auto: true  }, // 1 << 37
                    { active: false, id: 'add_reactions',            name: 'Add Reactions',             value: 0x40,         auto: true  }, // 1 << 6
                    { active: false, id: 'use_application_commands', name: 'Use Application Commands',  value: 0x80000000,   auto: true  }, // 1 << 31
                ]
            },
            {
                name: 'Voice',
                active: false,
                permissions: [
                    { active: false, id: 'connect',                 name: 'Connect',                 value: 0x100000,        auto: true }, // 1 << 20
                    { active: false, id: 'speak',                   name: 'Speak',                   value: 0x200000,        auto: true }, // 1 << 21
                    { active: false, id: 'stream',                  name: 'Video',                   value: 0x200,           auto: true }, // 1 << 9
                    { active: false, id: 'mute_members',            name: 'Mute Members',            value: 0x400000,        auto: true }, // 1 << 22
                    { active: false, id: 'deafen_members',          name: 'Deafen Members',          value: 0x800000,        auto: true }, // 1 << 23
                    { active: false, id: 'move_members',            name: 'Move Members',            value: 0x1000000,       auto: true }, // 1 << 24
                    { active: false, id: 'use_voice_activity',      name: 'Use Voice Activity',      value: 0x2000000,       auto: true }, // 1 << 25
                    { active: false, id: 'priority_speaker',        name: 'Priority Speaker',        value: 0x100,           auto: true }, // 1 << 8
                    { active: false, id: 'request_to_speak',        name: 'Request to Speak',        value: 0x100000000,     auto: true }, // 1 << 32
                    { active: false, id: 'use_embedded_activities', name: 'Use Embedded Activities', value: 0x8000000000,    auto: true }, // 1 << 39
                    { active: false, id: 'use_soundboard',          name: 'Use Soundboard',          value: 0x40000000000,   auto: true }, // 1 << 42
                    { active: false, id: 'use_external_sounds',     name: 'Use External Sounds',     value: 0x200000000000,  auto: true }, // 1 << 45
                    { active: false, id: 'send_voice_messages',     name: 'Send Voice Messages',     value: 0x400000000000,  auto: true }, // 1 << 46
                ]
            }
        ];

        if (!isNaN(perms))
        {
            for (let sectionId in $scope.permissions)
            {
                let section = $scope.permissions[sectionId];
                for (let permissionId in section.permissions)
                {
                    let permission = section.permissions[permissionId];
                    permission.active = (BigInt(perms) & BigInt(permission.value)) != 0;
                }
            }
        }
    }]);