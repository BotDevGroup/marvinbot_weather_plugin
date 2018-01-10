# -*- coding: utf-8 -*-

from marvinbot.utils import localized_date, get_message
from marvinbot.handlers import CommandHandler, CallbackQueryHandler
from marvinbot.plugins import Plugin
from marvinbot.models import User

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

import logging
import re
import requests
import ctypes
import time

log = logging.getLogger(__name__)


class MarvinBotWeatherPlugin(Plugin):
    def __init__(self):
        super(MarvinBotWeatherPlugin, self).__init__('marvinbot_weather_plugin')
        self.bot = None

    def get_default_config(self):
        maps = [ 
            ['Atlantic Wide','tatl'],['Western Atlantic','watl'],['Central Atlantic','catl'],
            ['Carribean','carb'],['Gulf of Mexico','gmex'],['Eastern United States','eaus'],
            ['Central United States','ceus'],['Northwest Atlantic','nwatl'],['North Atlantic','natl']
        ]
        code = {
            "0":"🌪","1":"⛈","2":"🌀","3":"⛈","4":"🌩","5":"🌨","6":"🌧","7":"🌧","8":"🌧","9":"🌧",
            "10":"🌧","11":"🌧","12":"🌧","13":"🌨","14":"🌨","15":"🌨","16":"🌨","17":"🌧","18":"🌧","19":"👽",
            "20":"👽","21":"👽","22":"👽","23":"🌬","24":"🌬","25":"❄","26":"☁","27":"☁","28":"🌤","29":"☁",
            "30":"🌤","31":"🌖","32":"🌝","33":"🌖","34":"🌝","35":"🌧","36":"🔥","37":"⛈","38":"⛈","39":"⛈",
            "40":"🌧","41":"🌨","42":"🌨","43":"🌨","44":"☁","45":"⛈","46":"🌨","47":"⛈",
            "3200":"👽"
        }
        return {
            'short_name': self.name,
            'enabled': True,
            'base_url': 'https://query.yahooapis.com/v1/public/yql',
            'maps': maps,
            'code': code,
        }

    def configure(self, config):
        self.config = config
        pass

    def setup_handlers(self, adapter):
        self.bot = adapter.bot
        self.add_handler(CommandHandler('weather', self.on_weather_command, command_description='Find current and forecast weather')
            .add_argument('--week', help='Find forecast weather by Yahoo! Weather', action='store_true')
            .add_argument('--map', help='Get IR AVN Map by NOAA', action='store_true')
            .add_argument('--hurricane', help='Hurricane Information by NOAA', action='store_true')
        )
        self.add_handler(CallbackQueryHandler('weather:', self.on_button), priority=1)
        self.add_handler(CallbackQueryHandler('map:', self.on_map), priority=1)

    def setup_schedules(self, adapter):
        pass

    def http(self, city="", woeid=""):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
            "Connection": "close"   
        }
        
        with requests.Session() as s:
            yql_query = ""
            payload = {}

            if woeid:
                yql_query = "select * from weather.forecast where woeid = '{}' and u='c'"
                payload["q"] = yql_query.format(woeid)
                payload["format"] = "json"
            else:
                yql_query = "select woeid,country,admin1 from geo.places where text = '{}' and placetype='country'"
                payload["q"] = yql_query.format(city)
                payload["format"] = "json"

            r = s.get(self.config.get('base_url'), params=payload)

            return r.json()

    def make_list(self, data):
        places = data['query']['results']['place'] if data['query']['count'] > 1 else [data['query']['results']['place']]
        countries = []
        for p in places:
            c = []

            if p['admin1'] is not None:
                t = "{} - {}".format(p['country']['content'], p['admin1']['content'])
            else:
                t = "{}".format(p['country']['content'])

            # plop!!! : )
            if not any(t in x for x in countries):
                c.append(p['woeid'])
                c.append(t)
                countries.append(c)

        return countries

    def make_msg(self, data):
        channel = data['query']['results']['channel'] 

        msg =  "*City*: {}\n".format(channel['location']['city'])
        msg += "*Country*: {}\n".format(channel['location']['country'])
        msg += "*Wind Speed*: {} km/h\n".format(channel['wind']['speed'])
        msg += "*Humidity*: {} %\n".format(channel['atmosphere']['humidity'])
        msg += "*Sunrise*: {}\n".format(time.strftime("%I:%M %p", time.strptime(channel['astronomy']['sunrise'], "%I:%M %p")))
        msg += "*Sunset*: {}\n".format(time.strftime("%I:%M %p", time.strptime(channel['astronomy']['sunset'], "%I:%M %p")))

        items = []
        
        i = "\n*Current*\n"
        i += "{} {}\n".format(
            self.config.get('code').get(channel['item']['condition']['code']),
            channel['item']['condition']['text']
        )
        i += "*Temp*: {} C".format(channel['item']['condition']['temp'])

        items.append(i)

        for forecast in channel['item']['forecast']:
            i = "\n\n*{}*\n".format(forecast['day'])
            i += "{} {}\n".format(
                self.config.get('code').get(forecast['code']),
                forecast['text']
            )
            i += "*Temp* Max: {} C, Min: {} C".format(forecast['high'], forecast['low'])

            items.append(i)

        r = {}
        r['msg'] = msg
        r['items'] = items

        return r

    def on_weather_command(self, update, *args, **kwargs):
        message = get_message(update)
        msg = ""
        reply_markup = ""
        
        map = kwargs.get('map', False)
        help = kwargs.get('help', False)
        week = kwargs.get('week', False)
        hurricane = kwargs.get('hurricane', False)

        if map:
            options = []

            for m in self.config.get('maps'):
                callback = "map:{}".format(m[1])
                options.append([InlineKeyboardButton(text=m[0], callback_data=callback)])

            reply_markup = InlineKeyboardMarkup(options)
            self.adapter.bot.sendMessage(chat_id=message.chat_id, text="🛰 Map:", reply_markup=reply_markup)
        elif hurricane:
            self.adapter.bot.sendMessage(chat_id=message.chat_id, text="⚠ Under construction", parse_mode='Markdown', disable_web_page_preview = True)
        else:
            try:
                cmd_args = re.sub('—\w*', '', message.text).split(" ")
                if len(cmd_args) > 1:
                    city = " ".join(cmd_args[1:])
                    data = self.http(city=city)

                    options = []

                    countries = self.make_list(data)

                    for c in countries:
                        d = "weather:{}:{}".format(c[0], week)
                        options.append([InlineKeyboardButton(text=c[1], callback_data=d)])

                    if len(options) > 0:
                        reply_markup = InlineKeyboardMarkup(options)
                    else:
                        msg = "❌ City not found"
                        reply_markup = ""
                else:
                    msg = "‼️ Use: /weather <city>"
            except Exception as err:
                log.error("Weather error: {}".format(err))
                msg = "❌ Error"

            if reply_markup:
                self.adapter.bot.sendMessage(chat_id=message.chat_id, text="☁️ Select:", reply_markup=reply_markup)
            else:
                self.adapter.bot.sendMessage(chat_id=message.chat_id, text=msg, parse_mode='Markdown', disable_web_page_preview = True)

    def on_button(self, update):
        query = update.callback_query
        data = query.data.split(":")
        msg = ""

        try:
            self.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)
        except:
            query.message.edit_reply_markup(reply_markup=None)

        try:
            r = self.http(woeid=data[1])
            m = self.make_msg(r)

            msg = m['msg']

            if "True" == data[2]:
                for i in m['items'][:5]:
                    msg += i
            else:
                msg += m['items'][0]
        except Exception as err:
            log.error("Weather button error: {}".format(err))
            msg = "❌ Error"
            
        self.adapter.bot.sendMessage(chat_id=query.message.chat_id, text=msg, parse_mode='Markdown', disable_web_page_preview = True)

    def on_map(self, update):
        query = update.callback_query
        data = query.data.split(":")
        msg = ""

        try:
            self.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)
        except:
            query.message.edit_reply_markup(reply_markup=None)

        try:
            url = "http://www.ssd.noaa.gov/goes/east/{}/avn-l.jpg".format(data[1])
            m = requests.get(url, stream=True, timeout=60)
            if m.status_code == 200:
                m.raw.decode_content = True
                self.adapter.bot.sendPhoto(chat_id=query.message.chat_id, photo=m.raw)
            else:
                msg = "❌ Download error"
        except requests.exceptions.Timeout as err:
            log.error("Weather map error: {}".format(err))
            msg = "❌ Connection timeout to NOAA"
        except Exception as err:
            log.error("Weather map error: {}".format(err))
            msg = "❌ Error"

        if msg:
            self.adapter.bot.sendMessage(chat_id=query.message.chat_id, text=msg, parse_mode='Markdown')
