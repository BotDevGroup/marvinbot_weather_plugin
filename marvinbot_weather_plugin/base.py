# -*- coding: utf-8 -*-

import marvinbot_weather_plugin.city as city
import marvinbot_weather_plugin.flag as flag
import marvinbot_weather_plugin.timezone as timezone

from marvinbot.utils import localized_date, get_message
from marvinbot.handlers import CommandHandler, CallbackQueryHandler
from marvinbot.plugins import Plugin
from marvinbot.models import User

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bs4 import BeautifulSoup
from io import StringIO

import logging
import re
import requests
import ctypes
import time
import xml.etree.ElementTree as ET
import traceback
import pytz

from datetime import datetime

log = logging.getLogger(__name__)

last = []
nhc = []

class MarvinBotWeatherPlugin(Plugin):
    def __init__(self):
        super(MarvinBotWeatherPlugin, self).__init__('marvinbot_weather_plugin')
        self.bot = None

    def get_default_config(self):
        maps = { 
            'noaa' : {
                'url' : 'https://cdn.star.nesdis.noaa.gov/GOES16/ABI/SECTOR/',
                'items' : [
                    [['Atlantic Wide - IR','taw/07/1800x1080.jpg'],['Atlantic Wide - Visible','taw/GEOCOLOR/1800x1080.jpg']],
                    [['Carribean - IR','car/07/1000x1000.jpg'],['Carribean - Visible','car/GEOCOLOR/1000x1000.jpg']],
                    [['Gulf of Mexico - IR','gm/07/1000x1000.jpg'],['Gulf of Mexico - Visible','gm/GEOCOLOR/1000x1000.jpg']],
                    [['US Atlantic Coast - IR','eus/07/1000x1000.jpg'],['US Atlantic Coast - Visible','eus/GEOCOLOR/1000x1000.jpg']],
                    [['Puerto Rico - IR','pr/07/1200x1200.jpg'],['Puerto Rico - Visible','pr/GEOCOLOR/1200x1200.jpg']]
                ]
            },
            'ca' : {
                'url' : 'https://weather.gc.ca/data/satellite/',
                'items' : [
                    [['Eastern Canada - IR','goes_ecan_1070_100.jpg'],['Eastern Canada - Visible','goes_ecan_visible_100.jpg']],
                    [['Western Canada - IR','goes_wcan_1070_100.jpg'],['Western Canada - Visible','goes_wcan_visible_100.jpg']]
                ]
            }
        }
        code = {
            '01d' : '☀',  '01n' : '🌕',        
            '02d' : '⛅', '02n' : '☁',         
            '03d' : '☁',  '03n' : '☁',        
            '04d' : '☁',  '04n' : '☁',        
            '09d' : '🌧', '09n' : '🌧',        
            '10d' : '🌧', '10n' : '🌧',        
            '11d' : '🌩', '11n' : '🌩',        
            '13d' : '🌨', '13n' : '🌨',        
            '50d' : '🌫', '50n' : '🌫'        
        }
        return {
            'short_name': self.name,
            'enabled': True,
            'base_url': 'https://api.openweathermap.org/data/2.5/weather',
            'maps': maps,
            'code': code,
            'timer': 15*60,
            'timeout': 120
        }

    def configure(self, config):
        self.config = config
        pass

    def setup_handlers(self, adapter):
        self.bot = adapter.bot
        self.add_handler(CommandHandler('weather', self.on_weather_command, command_description='Find current weather from OpenWeatherMap.'))
        self.add_handler(CommandHandler('satellite', self.on_satellite_command, command_description='Get Satellite View Map from NOAA.'))
        self.add_handler(CommandHandler('cyclones', self.on_hurricane_command, command_description='Cyclones Information from NOAA. (default: Atlantic)')
            .add_argument('--ep', help='Eastern North Pacific', action='store_true')
            .add_argument('--at', help='Atlantic', action='store_true')
        )
        self.add_handler(CallbackQueryHandler('weather:', self.on_button), priority=1)
        self.add_handler(CallbackQueryHandler('map:', self.on_map), priority=1)
        self.add_handler(CallbackQueryHandler('nhc:', self.on_nhc), priority=1)

    def setup_schedules(self, adapter):
        pass

    def http(self, city="", cityid=""):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
            "Connection": "close"   
        }
        
        with requests.Session() as s:
            payload = {}

            if cityid:
                payload["id"] = cityid
            else:
                payload["q"] = city

            payload["APPID"] = self.config.get('APPID')
            payload["units"] = self.config.get('units', 'standard')
            payload["lang"] = self.config.get('lang', 'us')

            r = s.get(self.config.get('base_url'), params=payload)

            return r.json()

    def http_nhc(self, ep=False):
        nhc = []

        url = "https://www.nhc.noaa.gov/index-{}.xml".format("ep" if ep else "at")
        r = requests.get(url, timeout=self.config.get('timeout'));
        
        # strip all namespaces
        tree = ET.iterparse(StringIO(r.text))
        for _, el in tree:
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]  
        
        root = tree.root
         
        for c in root.iter('Cyclone'):
            hurracane = {}
        
            hurracane['name'] = c.find('name').text
            hurracane['movement'] = c.find('movement').text
            hurracane['pressure'] = c.find('pressure').text
            hurracane['type'] = c.find('type').text
            hurracane['wind'] = c.find('wind').text
            hurracane['datetime'] = c.find('datetime').text
            hurracane['headline'] = c.find('headline').text.strip()
            hurracane['center'] = c.find('center').text
        
            for child in root.iter('item'):
                if('Graphics' in child.find('title').text and hurracane['name'] in child.find('title').text):
                    html_soup = BeautifulSoup(child.find('description').text, 'html.parser')
                    for img in html_soup.find_all('img'):
                        if '5day' in img['src']: hurracane['img-5day'] = img['src']
                        if 'wind' in img['src']: hurracane['img-wind'] = img['src']
        
            nhc.append(hurracane)

        return nhc

    def http_nesdis(self, center):
        def nesdisLatLon(url):
            return [float(x) for x in re.split('.*lat=(\d+)\w\&lon=(\d+)\w', url) if x != '']
        
        def nhcLatLon(center):
            return [float(x) for x in re.split('(\d+\.\d+)\,\s\-(\d+\.\d+)', center) if x != '']
        
        def compareLatLon(nhc, nesdis, rang=5):
            return nesdis[0] - rang <= nhc[0] <= nesdis[0] + rang and nesdis[1] - rang <= nhc[1] <= nesdis[1] + rang

        url = 'https://www.star.nesdis.noaa.gov/GOES/'

        nhclatlon = nhcLatLon(center)

        r = requests.get("{}{}".format(url,'MESO_index.php'), timeout=self.config.get('timeout'))
        
        html_soup = BeautifulSoup(r.text, 'html.parser')
        
        for ul in html_soup.find('div', id='tab1').find_all('ul', class_='mesoItems'):
            for li in ul.find_all('li'):
                if compareLatLon(nhclatlon, nesdisLatLon(li.a['href'])):
                    r2 = requests.get("{}{}".format(url, li.a['href']), timeout=self.config.get('timeout'))
                    html_soup2 = BeautifulSoup(r2.text, 'html.parser')
        
                    for tb in html_soup2.find_all('div', class_='TNBox'):
                        if 'Band 13' in tb.a['title']:
                            return tb.a['href']

        return ""

    def http_ssd(self):
        ssd = []

        url = 'http://www.ssd.noaa.gov/PS/TROP/floaters.html'
        r = requests.get(url, timeout=self.config.get('timeout'))
        
        html_soup = BeautifulSoup(r.text, 'html.parser')
        
        for tbody in html_soup.find_all('table'):
            for a in tbody.find_all('a'):
                if a.find('strong'):
                    avn = {}
                    avn['name'] = a.strong.text

                    link = a['href']
                    r2 = requests.get(link)
        
                    html_soup2 =  BeautifulSoup(r2.text, 'html.parser')
        
                    for img in html_soup2.find_all('img'):
                        avn['img'] = '{}{}'.format(url, img['src'])
        
                    ssd.append(avn)
        
        return ssd

    def http_stormcaribe(self, name):
        url = 'https://stormcarib.com/'

        r = requests.get(url, timeout=self.config.get('timeout'))
        
        html_soup = BeautifulSoup(r.text, 'html.parser')
        
        for tr in html_soup.find_all('tr'):
            if "tools" in tr.td.text and name.lower() in tr.td.text.lower():
                for a in tr.find_all('a', title='[Spaghetti plots + intensity]'):
                    r2 = requests.get("{}{}".format(url, a['href']), timeout=self.config.get('timeout'))
                    html_soup2 = BeautifulSoup(r2.text, 'html.parser')
                    return html_soup2.find_all('img')[1]['src']

        return ""

    def http_image(self, url):
        try: 
            if url:
                image = requests.get(url, stream=True, timeout=self.config.get('timeout'))
                if image.status_code == 200:
                    image.raw.decode_content = True
                    return image
        except Exception as err:
            log.error("Weather http_image url: {} error: {}".format(url, err))

        return ""

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
        temp_chart = {
            'metric': '°C',
            'imperial': '°F',
            'standard': '°K'
        }

        if data['cod'] != 200:
            return data['message']

        tz = pytz.timezone(timezone.Timezone().getTimezone(data['sys']['country']))

        msg =  "*{} {}*\n\n".format(data['name'], flag.Flag().getFlag(data['sys']['country']))
        
        for temp in data['weather']:
            msg += "{} {}\n".format(self.config.get('code').get(temp['icon']), temp['description'])

        msg += "\n"
        msg += "*Temp*: {} {}\n".format(data['main']['temp'], temp_chart.get(self.config.get('units'), "standard"))

        msg += "*Sunrise*: {}\n".format(datetime.fromtimestamp(int(data['sys']['sunrise']), tz).strftime("%I:%M %p"))
        msg += "*Sunset*: {}\n".format(datetime.fromtimestamp(int(data['sys']['sunset']), tz).strftime("%I:%M %p"))

        return msg

    def make_msg_nhc(self, hurracane):
        msg =  "🌀 *Name*: {}\n".format(hurracane['name'])
        msg += "🔺 *Type*: {}\n".format(hurracane['type'])
        msg += "➡ *Movement*: {}\n".format(hurracane['movement'])
        msg += "🌡 *Pressure*: {}\n".format(hurracane['pressure'])
        msg += "🌬 *Wind*: {}\n".format(hurracane['wind'])
        msg += "📝 *Headline*: {}\n".format(hurracane['headline'])
        msg += "⏳ *Date*: {}\n".format(hurracane['datetime'])

        return msg

    def on_satellite_command(self, update, *args, **kwargs):
        message = get_message(update)

        options = []

        for key in self.config.get('maps'):
            m = self.config.get('maps').get(key)
            for items in m.get('items'):
                options.append([InlineKeyboardButton(text=item[0], callback_data="map:{}:{}".format(item[1], key)) for item in items])

        reply_markup = InlineKeyboardMarkup(options)
        self.adapter.bot.sendMessage(chat_id=message.chat_id, text="🛰 Maps:", reply_markup=reply_markup)

    def on_weather_command(self, update, *args, **kwargs):
        def chunks(l, n):
            return list(l[i:i+n] for i in range(0, len(l), n))

        message = get_message(update)
        msg = ""
        reply_markup = ""

        try:
            cmd_args = re.sub('—\w*', '', message.text).split(" ")
            if len(cmd_args) > 1:
                name = " ".join(cmd_args[1:])

                cities = city.City().getCity(name)
                options = []
                
                options = chunks([InlineKeyboardButton(text='{} {}'.format(c['name'], flag.Flag().getFlag(c['country'])), callback_data="weather:{}".format(c['id'])) for c in cities], 3)

                if len(options) > 0:
                    options.append([InlineKeyboardButton(text="Cancel", callback_data="weather:__cancel__")])
                    reply_markup = InlineKeyboardMarkup(options)
                else:
                    msg = "❌ City not found"
                    reply_markup = ""
            else:
                msg = "‼️ Use: /weather <city>"
        except Exception as err:
            log.error("Weather error: {}".format(err))
            traceback.print_exc()

        if reply_markup:
            self.adapter.bot.sendMessage(chat_id=message.chat_id, text="☁️ Select:", reply_markup=reply_markup)
        else:
            self.adapter.bot.sendMessage(chat_id=message.chat_id, text=msg, parse_mode='Markdown', disable_web_page_preview = True)

    def on_hurricane_command(self, update, *args, **kwargs):
        global nhc

        ep = kwargs.get('ep', False)

        message = get_message(update)
        msg = ""
        reply_markup = ""

        try:
            nhc = self.http_nhc(ep=ep)

            options = []

            for hurricane in nhc:
                callback = "nhc:{}".format(hurricane['name'])
                options.append([InlineKeyboardButton(text=hurricane['name'], callback_data=callback)])

            url = "https://www.nhc.noaa.gov/xgtwo/two_{}_0d0.png".format("pac" if ep else "atl")
            map = self.http_image(url)
            if map:
                self.adapter.bot.sendPhoto(chat_id=message.chat_id, photo=map.raw)

            if len(options) > 0:
                reply_markup = InlineKeyboardMarkup(options)
            else:
                msg = "🔵 There are no tropical cyclones at this time."
                reply_markup = ""
        except Exception as err:
            log.error("Weather error: {}".format(err))

        if reply_markup:
            self.adapter.bot.sendMessage(chat_id=message.chat_id, text="🌀 Select:", reply_markup=reply_markup)
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
            if data[1] == "__cancel__":
                return
            msg = self.make_msg(self.http(cityid=data[1]))
        except Exception as err:
            log.error("Weather button error: {}".format(err))
            
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
            url = "{}{}".format(self.config.get('maps').get(data[2]).get('url'), data[1])
            m = self.http_image(url)
            if m:
                self.adapter.bot.sendPhoto(chat_id=query.message.chat_id, photo=m.raw)
            else:
                msg = "❌ Download error"
        except requests.exceptions.Timeout as err:
            log.error("Weather map error: {}".format(err))
        except Exception as err:
            log.error("Weather map error: {}".format(err))

        if msg:
            self.adapter.bot.sendMessage(chat_id=query.message.chat_id, text=msg, parse_mode='Markdown')

    def on_nhc(self, update):
        global nhc
        global last

        query = update.callback_query
        data = query.data.split(":")

        try:
            self.bot.deleteMessage(chat_id=query.message.chat_id, message_id=query.message.message_id)
        except:
            query.message.edit_reply_markup(reply_markup=None)

        last = [x for x in last if x['date'] + self.config.get("timer") > time.time()]
        old_message = next((x for x in last if x['chat_id'] == query.message.chat_id and x['hurricane'] == data[1]), None)

        fiveday = ""
        avn = ""
        nesdis = ""
        stormcarib = ""

        try:
            hurricane = next((hurricane for hurricane in nhc if hurricane['name'] == data[1]), None)
            if hurricane:
                if old_message and old_message['date'] + self.config.get("timer") > time.time():
                    msg_replay = "#Cyclone last info!"
                    self.adapter.bot.sendMessage(chat_id=query.message.chat_id, reply_to_message_id=old_message['message_id'], text=msg_replay, parse_mode='Markdown', disable_web_page_preview = True)
                else:
                    msg_nhc = self.make_msg_nhc(hurricane)

                    if 'img-5day' in hurricane:
                        fiveday = self.http_image(hurricane['img-5day'])

                    ssd = next((ssd for ssd in self.http_ssd() if ssd['name'] == hurricane['name']), None)
                    if ssd:
                        avn = self.http_image(ssd['img'])

                    nesdis = self.http_image(self.http_nesdis(hurricane['center']))
                    stormcarib = self.http_image(self.http_stormcaribe(hurricane['name']))

                    last_message = self.adapter.bot.sendMessage(chat_id=query.message.chat_id, text=msg_nhc, parse_mode='Markdown')  
                    if fiveday: self.adapter.bot.sendPhoto(chat_id=query.message.chat_id, photo=fiveday.raw)
                    if avn: self.adapter.bot.sendPhoto(chat_id=query.message.chat_id, photo=avn.raw)
                    if nesdis: self.adapter.bot.sendPhoto(chat_id=query.message.chat_id, photo=nesdis.raw)
                    if stormcarib: self.adapter.bot.sendPhoto(chat_id=query.message.chat_id, photo=stormcarib.raw)
                    if old_message:
                        last.remove(old_message)
                    last.append({'date': time.time(), 'chat_id': query.message.chat_id, 'message_id': last_message.message_id, 'hurricane': data[1]})
            else:
                msg = "❌ Not hurricane"
                self.adapter.bot.sendMessage(chat_id=query.message.chat_id, text=msg, parse_mode='Markdown')
        except Exception as err:
            log.error("Weather nhc/ssd error: {}".format(err))

