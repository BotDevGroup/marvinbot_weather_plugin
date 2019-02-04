# Marvinbot Weather Plugin

OpenWeatherMap and National Hurricane Center NOAA

# Requirements

-   A working [Marvinbot](https://github.com/BotDevGroup/marvin) install

# Getting Started

## Configuration

Unit
 - *standard* Kelvin (default)
 - *metric* Celsius
 - *imperial* Fahrenheit

Lang

Arabic - ar, Bulgarian - bg, Catalan - ca, Czech - cz, German - de, Greek - el, English - en, Persian (Farsi) - fa, Finnish - fi, French - fr, Galician - gl, Croatian - hr, Hungarian - hu, Italian - it, Japanese - ja, Korean - kr, Latvian - la, Lithuanian - lt, Macedonian - mk, Dutch - nl, Polish - pl, Portuguese - pt, Romanian - ro, Russian - ru, Swedish - se, Slovak - sk, Slovenian - sl, Spanish - es, Turkish - tr, Ukrainian - ua, Vietnamese - vi, Chinese Simplified - zh_cn, Chinese Traditional - zh_tw.

Open your marvinbot settings.json and add in plugin_configuration:

```
    "marvinbot_weather_plugin" : {
        "APPID" : "YOURAPIKEY",
        "units" : "metric",
        "lang" : "es"
    } 
```