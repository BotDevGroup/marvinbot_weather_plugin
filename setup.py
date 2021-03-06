from distutils.core import setup
from setuptools import find_packages

REQUIREMENTS = [
    'marvinbot',
    'python-Levenshtein',
    'timezonefinder'
]

setup(name='marvinbot-weather-plugin',
      version='0.3',
      description='Weather from OpenWeatherMap and NOAA',
      author='Conrado Reyes',
      author_email='coreyes@gmail.com',
      url='',
      packages=[
        'marvinbot_weather_plugin',
      ],
      package_dir={
        'marvinbot_weather_plugin':'marvinbot_weather_plugin'
      },
      zip_safe=False,
      include_package_data=True,
      package_data={'': ['*.ini']},
      install_requires=REQUIREMENTS,
      dependency_links=[
          'git+ssh://git@github.com:BotDevGroup/marvin.git#egg=marvinbot',
      ],
)
