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
                    return `https://discordapp.com/oauth2/authorize/?permissions=${permissions}&scope=bot&client_id=${info.id}&response_type=code`;
                else if(!info.hasScope)
                    return `https://discordapp.com/oauth2/authorize/?permissions=${permissions}&scope=bot&client_id=${info.id}`;
                else if (info.hasCode)
                    return `https://discordapp.com/oauth2/authorize/?permissions=${permissions}&scope=${info.scope}&client_id=${info.id}&response_type=code`;
                else
                    return `https://discordapp.com/oauth2/authorize/?permissions=${permissions}&scope=${info.scope}&client_id=${info.id}`;
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
            let value = 0;
            for (let sectionId in $scope.permissions)
            {
                let section = $scope.permissions[sectionId];
                for (let permissionId in section.permissions)
                {
                    let permission = section.permissions[permissionId];
                    if (permission.active)
                    {
                        value |= permission.value;
                    }
                }
            }
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
                    {active: false, id: 'administrator',    name: 'Administrator',         value: 0x8,        auto: false},
                    {active: false, id: 'manage_roles',     name: 'Manage Roles',          value: 0x10000000, auto: false},
                    {active: false, id: 'kick_members',     name: 'Kick Members',          value: 0x2,        auto: false},
                    {active: false, id: 'instant_invite',   name: 'Create Instant Invite', value: 0x1,        auto: true },
                    {active: false, id: 'manage_nicknames', name: 'Manage Nicknames',      value: 0x8000000,  auto: true },
                    {active: false, id: 'manage_server',    name: 'Manage Server',         value: 0x20,       auto: false},
                    {active: false, id: 'manage_channels',  name: 'Manage Channels',       value: 0x10,       auto: false},
                    {active: false, id: 'ban_members',      name: 'Ban Members',           value: 0x4,        auto: false},
                    {active: false, id: 'change_nickname',  name: 'Change Nickname',       value: 0x4000000,  auto: true },
                    {active: false, id: 'manage_webhooks',  name: 'Manage Webhooks',       value: 0x20000000, auto: false},
                    {active: false, id: 'manage_emojis',    name: 'Manage Emojis',         value: 0x40000000, auto: true },
                    {active: false, id: 'view_audit_log',   name: 'View Audit Log',        value: 0x80,       auto: true },
                    {active: false, id: 'view_channel',     name: 'View Channel',          value: 0x400,      auto: true }
                ]
            },
            {
                name: 'Text',
                active: false,
                permissions: [
                    {active: false, id: 'send_tts_messages',    name: 'Send TTS Messages',    value: 0x1000,  auto: true },
                    {active: false, id: 'embed_links',          name: 'Embed Links',          value: 0x4000,  auto: true },
                    {active: false, id: 'read_message_history', name: 'Read Message History', value: 0x10000, auto: true },
                    {active: false, id: 'use_external_emojis',  name: 'Use External Emojis',  value: 0x40000, auto: true },
                    {active: false, id: 'send_messages',        name: 'Send Messages',        value: 0x800,   auto: true },
                    {active: false, id: 'manage_messaes',       name: 'Manage Messages',      value: 0x2000,  auto: false},
                    {active: false, id: 'attach_files',         name: 'Attach Files',         value: 0x8000,  auto: true },
                    {active: false, id: 'mention_everyone',     name: 'Mention Everyone',     value: 0x20000, auto: true },
                    {active: false, id: 'add_reactions',        name: 'Add Reactions',        value: 0x40,    auto: true }
                ]
            },
            {
                name: 'Voice',
                active: false,
                permissions: [
                    {active: false, id: 'connect',            name: 'Connect',            value: 0x100000,  auto: true },
                    {active: false, id: 'mute_members',       name: 'Mute Members',       value: 0x400000,  auto: true },
                    {active: false, id: 'move_members',       name: 'Move Members',       value: 0x1000000, auto: true },
                    {active: false, id: 'speak',              name: 'Speak',              value: 0x200000,  auto: true },
                    {active: false, id: 'deafen_members',     name: 'Deafen Members',     value: 0x800000,  auto: true },
                    {active: false, id: 'use_voice_activity', name: 'Use Voice Activity', value: 0x2000000, auto: true }
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
                    permission.active = (perms & permission.value) != 0;
                }
            }
        }
    }]);
