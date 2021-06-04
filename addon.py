from bs4 import BeautifulSoup
from time import time
import sys
import os
import requests
import urllib.parse
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/81.0.4044.138 Safari/537.36'}

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
data_dir = xbmc.translatePath(__addon__.getAddonInfo('profile'))

base_url = sys.argv[0]
__addon_handle__ = int(sys.argv[1])
args = urllib.parse.parse_qs(sys.argv[2][1:])
lang = "de" if xbmc.getLanguage(xbmc.ISO_639_1) == "de" else "en"

xbmcplugin.setContent(__addon_handle__, 'videos')


def build_url(query):
    """Get the addon url based on Kodi request"""

    return f"{base_url}?{urllib.parse.urlencode(query)}"


def load_channels():
    """Load the channel list"""

    channels = dict()

    for web_type in ("show", "sport"):
        url = f"https://{web_type}.sky.ch/de/live-auf-tv" if lang == "de" else \
            f"https://{web_type}.sky.ch/en/live-of-tv"
        live_page = requests.get(url, headers=headers, cookies={"SkyCookie": login()})

        parse_live_page = BeautifulSoup(live_page.content, 'html.parser')

        for item in parse_live_page.findAll("li", {"class": "epg-channel-list-item"}):
            channel_disabled = True if len(item.findAll("div", {"class": "option-tag"})) > 0 else False
            if channel_disabled is False:
                for link in item.findAll("a", {"class": "epg-channel-link"}):
                    for name in link.findAll("img"):
                        channels.update({link["data-id"]: name["alt"]})

    channel_listing = []
    for item in channels.keys():
        url = build_url({'play': '4', 'id': item})
        li = xbmcgui.ListItem(channels[item])
        li.setArt({"thumb": f"https://s3.sky.ch/img/moviecover/ch/images/channel/{item}.png"})
        channel_listing.append((url, li, False))

    xbmcplugin.addDirectoryItems(__addon_handle__, channel_listing, len(channel_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)


def load_categories(content_type):
    """Retrieve a list of all categories"""

    url = f"https://show.sky.ch/de/{'filme' if content_type == 'movie' else 'serien'}" \
        if lang == "de" else f"https://show.sky.ch/en/{'movies' if content_type == 'movie' else 'tv-series'}"
    home_page = requests.get(url, headers=headers, cookies={"SkyCookie": login()})

    parse_home_page = BeautifulSoup(home_page.content, 'html.parser')
    category_listing = []

    for div_poster_container in parse_home_page.findAll(
            "div", {"class": f"poster-container-{'film' if content_type == 'movie' else 'serie'}"}):
        for detail in div_poster_container.findAll("div", {"class": "details"}):
            category_listing.append([item.text.replace("\n", "").replace("  ", "") for item in detail.findAll("p")][2])
    category_listing = sorted(list(set(category_listing)))
    category_listing.insert(0, "Alle" if lang == "de" else "All")

    menu_listing = []
    for category in category_listing:
        li = xbmcgui.ListItem(label=category)
        url = build_url({'mode': content_type, 'category': category})
        menu_listing.append((url, li, True))

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)


def load_contents(content_type, category):
    """Retrieve all movie/series items mentioned on webpage"""

    url = f"https://show.sky.ch/de/{'filme' if content_type == 'movie' else 'serien'}" if lang == "de" else \
        f"https://show.sky.ch/en/{'movies' if content_type == 'movie' else 'tv-series'}"
    home_page = requests.get(url, headers=headers, cookies={"SkyCookie": login()})

    parse_home_page = BeautifulSoup(home_page.content, 'html.parser')
    menu_listing_prepare = []

    for div_poster_container in parse_home_page.findAll(
            "div", {"class": f"poster-container-{'film' if content_type == 'movie' else 'serie'}"}):
        menu_dict = dict()
        for div_poster in div_poster_container.findAll("div", {"class": "poster"}):
            menu_dict["id"] = div_poster["data-id"]
        for link in div_poster_container.findAll("a", {"href": "#"}):
            if link.get("data-url") is not None:
                menu_dict["url"] = link["data-url"]
        for img_container in div_poster_container.findAll("div", {"class": "img-container"}):
            for img in img_container.findAll("img"):
                menu_dict["img"] = img["src"]
        for title in div_poster_container.findAll("p", {"class": "title"}):
            menu_dict["title"] = title.text.replace("\n", "").replace("  ", "")
        if menu_dict.get("title") is None:
            for title in div_poster_container.findAll("span", {"class": "title"}):
                menu_dict["title"] = title.text.replace("\n", "").replace("  ", "")
        index = 0
        for detail in div_poster_container.findAll("div", {"class": "details"}):
            details = dict()
            info_types = ["year", "duration", "genre"] if content_type == "movie" else ["year", "content", "genre"]
            for item in detail.findAll("p"):
                details[info_types[index]] = item.text.replace("\n", "").replace("  ", "")
                index = index + 1
            menu_dict["details"] = details
        menu_listing_prepare.append(menu_dict)

    menu_listing = []
    for item in menu_listing_prepare:
        if category == item["details"]["genre"] or category == f"{'Alle' if lang == 'de' else 'All'}":
            li = xbmcgui.ListItem(label=item['title'])
            li.setArt({"thumb": item["img"]})
            if item["details"].get("duration", False):
                li.setInfo('video', {'title': item["title"], 'genre': item["details"]["genre"],
                                     'year': int(item["details"]["year"]),
                                     'duration': int(item["details"]["duration"].replace(" mn", "")) * 60})
            else:
                li.setInfo('video', {'title': item["title"], 'genre': item["details"]["genre"],
                                     'year': int(item["details"]["year"])})
            url = build_url({'mode': content_type, 'id': item["id"], "url": item["url"]})
            menu_listing.append((url, li, True))

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)


def load_content_details(content_type, content_id, content_url):
    """Get advanced movie/series details"""

    url = f"https://show.sky.ch{content_url}"
    tv_details = requests.get(url, headers=headers, cookies={"SkyCookie": login()})

    parse_content_page = BeautifulSoup(tv_details.content, 'html.parser')

    menu_dict = dict()

    menu_dict["fan_art"] = f"https://s3.sky.ch/img/moviecover/ch/images/scenes/{content_id}/1_1280x720.jpg"
    menu_dict["img"] = f"https://s3.sky.ch/img/moviecover/ch/images/logo/png/{content_id}_600w.png"

    for title in parse_content_page.findAll("h1"):
        menu_dict["title"] = title.text.replace("\n", "").replace("  ", "")
    for desc in parse_content_page.findAll("p", {"id": "pageMetadatasSummary"}):
        menu_dict["desc"] = desc.text.replace("\n", "").replace("  ", "")
    details = dict()
    index = 0
    info_types = ["year", "duration", "genre"]
    for detail in parse_content_page.findAll("span", {"class": "mr-16"}):
        details[info_types[index]] = detail.text.replace("\n", "").replace("  ", "")
        index = index + 1
    menu_dict["details"] = details
    details = dict()
    index = 0
    info_types = ["director", "actor"]
    for cast in parse_content_page.findAll("div", {"id": "pageMetadatasInfoMetadatas"}):
        for cast_type in cast.findAll("ul"):
            details[info_types[index]] = []
            for name in cast_type.findAll("li"):
                details[info_types[index]].append(
                    name.text.replace("\n", "").replace("  ", "").replace(',\xa0', ""))
            index = index + 1
            if index == 2:
                break
    menu_dict["cast"] = details

    menu_listing = []

    # MOVIE
    if content_type == "movie":

        # TRAILER + MOVIE
        details_listing_prepare = [("Film", "2"), ("Trailer", "3")] \
            if lang == "de" else [("Movie", "2"), ("Trailer", "3")]

        for item in details_listing_prepare:
            if item[0] == "Trailer":
                duration = 3
            else:
                duration = int(menu_dict["details"]["duration"].replace("mn", ""))
            li = xbmcgui.ListItem(label=f'{item[0]}: {menu_dict["title"]}')
            li.setArt({"thumb": menu_dict["img"], "fanart": menu_dict["fan_art"]})
            li.setInfo('video', {'title': menu_dict["title"], 'genre': menu_dict["details"]["genre"],
                                 'year': int(menu_dict["details"]["year"]), 'plot': menu_dict["desc"],
                                 'director': menu_dict["cast"]["director"], 'cast': menu_dict["cast"]["actor"],
                                 'duration': duration * 60})
            url = build_url({'id': content_id, "play": item[1]})
            menu_listing.append((url, li, False))

    # SERIES
    else:
        content_dict = dict()

        # TRAILER
        content_dict.update({content_id: {"type": "3"}})
        content_dict[content_id].update(
            {"fan_art": menu_dict["fan_art"], "img": menu_dict["img"], "title": f'Trailer: {menu_dict["title"]}',
             "genre": menu_dict["details"]["genre"], "year": menu_dict["details"]["year"],
             "desc": menu_dict["desc"], "director": menu_dict["cast"]["director"], "cast": menu_dict["cast"]["actor"],
             "duration": 3})

        # EPISODES
        for item in parse_content_page.findAll("ul", {"id": "seasonSelectDropdownMobile"}):
            index = 0
            for season in item.findAll("li"):
                index = index + 1

                url = f"https://show.sky.ch{content_url}/{season['data-link']}"
                tv_details = requests.get(url, headers=headers, cookies={"SkyCookie": login()})

                parse_season_page = BeautifulSoup(tv_details.content, 'html.parser')

                for episode in parse_season_page.findAll("li", {"class": "episode-section"}):
                    content_dict.update({episode["data-id"]: {"type": "2"}})
                    content_dict[episode["data-id"]].update({
                        "fan_art":
                            f"https://s3.sky.ch/img/moviecover/ch/images/scenes/{episode['data-id']}/1_1280x720.jpg",
                        "img": menu_dict["img"], "year": menu_dict["details"]["year"],
                        "director": menu_dict["cast"]["director"], "cast": menu_dict["cast"]["actor"]})
                    for title in episode.findAll("h5"):
                        content_dict[episode["data-id"]].update(
                            {"title": "{} {} - {}".format('Staffel' if lang == "de" else "Season", index,
                                                          title.text.replace("  ", "").replace("\n", ""))})
                    for duration in episode.findAll("time"):
                        content_dict[episode["data-id"]].update(
                            {"duration": duration.text.replace("  ", "").replace("\n", "").replace(" min", "")})
                    for desc in episode.findAll("p", {"class": "text-14"}):
                        content_dict[episode["data-id"]].update({"desc": desc.text.replace("  ", "").replace("\n", "")})

        # BONUS CONTENT
        for item in parse_content_page.findAll("div", {"id": "bonusesContent"}):
            for list_item in item.findAll("li"):
                data_id = None
                for bonus in list_item.findAll("a", {"class": "play-bonus"}):
                    data_id = bonus["data-id"]
                    content_dict.update({bonus["data-id"]: {"type": "7"}})
                    content_dict[bonus["data-id"]].update({
                        "fan_art":
                            f"https://s3.sky.ch/img/images/videos/{bonus['data-id']}.jpg",
                        "img": menu_dict["img"], "year": menu_dict["details"]["year"],
                        "director": menu_dict["cast"]["director"], "cast": menu_dict["cast"]["actor"],
                        "desc": ""
                    })
                if data_id:
                    for title in list_item.findAll("h5"):
                        content_dict[data_id].update(
                            {"title": "{} - {}".format('Bonus' if lang == "de" else "Extra",
                                                       title.text.replace("  ", "").replace("\n", ""))})
                    for duration in list_item.findAll("time"):
                        content_dict[data_id].update(
                            {"duration": duration.text.replace("  ", "").replace("\n", "").replace(" min", "")})

        for item in content_dict.keys():
            li = xbmcgui.ListItem(label=content_dict[item]['title'])
            li.setArt({"thumb": content_dict[item]["img"], "fanart": content_dict[item]["fan_art"]})
            li.setInfo('video', {'title': content_dict[item]["title"], 'genre': menu_dict["details"]["genre"],
                                 'year': int(menu_dict["details"]["year"]), 'plot': content_dict[item]["desc"],
                                 'director': menu_dict["cast"]["director"], 'cast': menu_dict["cast"]["actor"],
                                 'duration': int(content_dict[item]["duration"]) * 60})
            url = build_url({'id': item, "play": content_dict[item]["type"]})
            menu_listing.append((url, li, False))

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)


def get_stream(channel_id, content_type):
    """Retrieve the live tv playlist"""

    url = f"https://show.sky.ch/{lang}/SkyPlayerAjax/SkyPlayer?id={channel_id}&contentType={content_type}"
    new_header = headers
    new_header['x-requested-with'] = 'XMLHttpRequest'

    tv = requests.get(url, headers=new_header, cookies={"SkyCookie": login()})
    tv_json = tv.json()

    if tv_json["Success"]:
        stream_url = tv_json["Url"]
        license_url = tv_json["LicenseUrl"]
        return stream_url, license_url
    else:
        xbmcgui.Dialog().notification(__addonname__, "Failed to retrieve the stream. "
                                                     "Please check your credentials/subscriptions.",
                                      xbmcgui.NOTIFICATION_ERROR)


def playback(stream_url, license_url):
    """Pass the urls to the player"""

    li = xbmcgui.ListItem(path=stream_url)

    if license_url is not None:
        li.setProperty('inputstream.adaptive.license_key', license_url + "||a{SSM}|")
        li.setProperty('inputstream.adaptive.license_type', "com.widevine.alpha")

    li.setProperty('inputstream', 'inputstream.adaptive')
    li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
    li.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(__addon_handle__, True, li)

    xbmc.Player().play(item=stream_url, listitem=li)


def router(item):
    """Router function calling other functions of this script"""

    params = dict(urllib.parse.parse_qsl(item[1:]))

    if params:

        # LIVE TV CHANNEL LIST
        if params.get("mode") == "live":
            load_channels()

        # MOVIE/SERIES DETAILS
        elif params.get("mode") and params.get("id") and params.get("url"):
            load_content_details(params["mode"], params["id"], params["url"])

        # MOVIE/SERIES LIST
        elif params.get("mode") and params.get("category"):
            load_contents(params["mode"], params["category"])

        # MOVIE/SERIES CATEGORY LIST
        elif params.get("mode"):
            load_categories(params["mode"])

        # LIVE TV / VOD STREAM
        elif params.get("play") and params.get("id"):
            stream_params = get_stream(params["id"], params["play"])
            if stream_params:
                playback(stream_params[0], stream_params[1])

    else:
        # MAIN
        main_listing = []
        for mode in [("live", "Live TV"), ("movie", "Cinema VoD"), ("show", "Entertainment VoD")]:
            url = build_url({'mode': mode[0]})
            li = xbmcgui.ListItem(mode[1])
            main_listing.append((url, li, True))

        xbmcplugin.addDirectoryItems(__addon_handle__, main_listing, len(main_listing))
        xbmcplugin.endOfDirectory(__addon_handle__)


def login():
    """Retrieve the session cookie to access the video content"""

    # Retrieve existing cookie from file
    if os.path.exists(f"{data_dir}/cookie.txt"):
        if (int(os.path.getmtime(f"{data_dir}/cookie.txt")) - int(time())) > 3600:
            os.remove(f"{data_dir}/cookie.txt")
        else:
            with open(f"{data_dir}/cookie.txt", "r") as file:
                cookie = file.read()
                file.close()
                return cookie

    # Check service country
    url = "https://sky.ch"
    check_page = requests.get(url, headers=headers)
    if "out-of-country" in check_page.url:
        xbmcgui.Dialog().notification(__addonname__, "Out of country, please check your IP address.",
                                      xbmcgui.NOTIFICATION_ERROR)
        return ""

    # Get username and password
    __login = __addon__.getSetting("username")
    __password = __addon__.getSetting("password")
    if __login == "" or __password == "":
        xbmcgui.Dialog().notification(__addonname__,
                                      "Failed to retrieve the credentials. Please check the addon settings.",
                                      xbmcgui.NOTIFICATION_ERROR)
        return ""

    # Login to webservice
    login_url = f'https://www.sky.ch/{lang}/login'
    login_page = requests.get(login_url, timeout=5, headers=headers)

    cookie_token = login_page.cookies.get("__RequestVerificationToken", None)
    login_page_parse = BeautifulSoup(login_page.content, 'html.parser')
    app_token_reference = login_page_parse.find('input', {'name': '__RequestVerificationToken'})
    page_token = app_token_reference.get("value", None)
    cookie = {"__RequestVerificationToken": cookie_token}

    data = {'username': __login, 'password': __password, 'rememberMe': 'on', 'mode': '',
            'returnUrl': '', 'subscriptionUrl': '/de/subscription', 'hasHomeMadeCaptcha': 'false',
            '__RequestVerificationToken': page_token}

    login_page = requests.post(login_url, timeout=5, headers=headers, cookies=cookie, data=data,
                               allow_redirects=False)

    cookie = login_page.cookies.get("SkyCookie", None)

    if cookie is None:
        xbmcgui.Dialog().notification(__addonname__,
                                      "Failed to retrieve the session cookie. Please check your credentials.",
                                      xbmcgui.NOTIFICATION_ERROR)
        return ""
    else:
        with open(f"{data_dir}/cookie.txt", "w") as file:
            file.write(cookie)
            file.close()
        return cookie


if __name__ == "__main__":
    router(sys.argv[2])
