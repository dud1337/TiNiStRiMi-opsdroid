######################################################################
#   
#   TiNiStRiMi notifier bot
#   TiNiStRiMi - https://github.com/dud1337/TiNiStRiMi
#       monitors TiNiStRiMi instance and notifies a chatroom
#   
#   1. Avoid spamming
#   2. Stream grabbing
#
######################################################################
from aiohttp.web import Request
from opsdroid.skill import Skill
from opsdroid.matchers import match_regex, match_crontab, match_event, match_webhook, match_always
from opsdroid.events import Message, Reaction, Image, Video, RoomDescription

from asyncio import sleep

import datetime
import requests

class tinistrimiMonitor(Skill):
    def __init__(self, *args, **kwargs):
        super(tinistrimiMonitor, self).__init__(*args, **kwargs)
        self.bot_was_last_message = False
        self.hook_in_use = False
        self.hook_flicker = datetime.datetime.today()

        self.bot_thinks_stream_is_up = self.check_stream_status()

        if self.bot_thinks_stream_is_up:
            # assume stream started an hour ago to force notification
            self.stream_since_when = datetime.datetime.today() - datetime.timedelta(hours=1)
        else:
            self.stream_since_when = False


    ##################################################################
    #
    #   1. Avoid spamming
    #       The bot notifies if a stream is ongoing every hour
    #       if no one posts within that hour, it is superfluous;
    #       this functionality prevents that.
    #
    ##################################################################
    async def avoid_spam_send(self, msg):
        if not self.bot_was_last_message:
            await self.opsdroid.send(
                Message(
                    text=msg,
                    target=self.config.get('room_notify')
                )
            )
            self.bot_was_last_message = True
        else:
            pass

    @match_always
    async def who_last_said(self, event):
        if hasattr(event, 'target') and event.target == self.config.get('room_notify'):
            self.bot_was_last_message = False


    ##################################################################
    #
    #   1. Stream monitoring
    #       Monitors stream
    #
    ##################################################################
    def check_stream_status(self):
        try:
            response = requests.get(self.config.get('stream_status_url'))
            if response.status_code == 200:
                data = response.json()
                status = data.get('status') == 'online'
            else:
                status = False
        except Exception as e:
            print(f"Error fetching stream status: {e}")
            status = False
        return status

    def take_stream_screenshot(self):
        pass

    @match_webhook('update')
    async def streamwebhookskill(self, event: Request):
        if self.hook_in_use:
            self.hook_flicker = datetime.datetime.today()
            return
        else:
            self.hook_in_use = True

        # Capture the post data
        data = await event.json()

        # wait 30 s to see if this is a flicker
        # sometimes OBS will spam messages, wait longer if so
        await sleep(30)
        while datetime.datetime.today() - self.hook_flicker < datetime.timedelta(seconds=10):
            await sleep(5)

        status = self.check_stream_status

        if data['stream_state_change'] == 'start' and status:
            await self.opsdroid.send(
                Message(
                    text='<h1>⚡️ STARTED <a href="https://matrix.to/#/#stream:138.io">#stream:138.io</a> <a href="' + self.config.get('stream_url') + '">STREAMIN\'</a> ⚡️</h1>',
                    target=self.config.get('room_notify')
                )
            )

            self.bot_was_last_message = True
            self.bot_thinks_stream_is_up = True
            self.stream_since_when = datetime.datetime.today()
        elif data['stream_state_change'] == 'stop' and not status:
            await self.opsdroid.send(
                Message(
                    text='<h1>⚰️ STREAM OVER ⚰️</h1>',
                    target=self.config.get('room_notify')
                )
            )
            self.bot_was_last_message = True
            self.bot_thinks_stream_is_up = False
            self.stream_since_when = False

        self.hook_in_use = False

    @match_crontab('* * * * *', timezone="Europe/Zurich")
    async def stream_ongoing(self, event):
        if self.bot_thinks_stream_is_up:
            await sleep(30)
            stream_up = self.check_stream_status()
            if stream_up:
                if (datetime.datetime.today() - self.stream_since_when) > datetime.timedelta(hours=1):
                    await self.avoid_spam_send(
                        '<h1>⚡️ <a href="' + self.config.get('stream_url') + '">STREAMIN\'</a> ⚡️</h1>'
                    )
                    self.stream_since_when = datetime.datetime.today()
            else:
                self.bot_thinks_stream_is_up = False
