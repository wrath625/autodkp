import requests
import pytz
from pytz import reference
import sys
import re
import aiohttp
import json
import asyncio
from dateutil import parser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import glob
import os


import sys
import pytesseract
from PIL import Image
from PIL import ImageGrab

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


io_pool_exc = ThreadPoolExecutor()

USERNAME = sys.argv[1]
PASSWORD = sys.argv[2]

BOSSES = {
    "The Prophet Skeram": {
        "name": ["The Prophet Skeram"],
        "count": 1,
        "dkp": 20
    },
    "Silithid Royalty": {
        "name": ["Lord Kri", "Vem", "Princess Yauj"],
        "count": 3,
        "dkp": 20
    },
    "Fankriss the Unyielding": {
        "name": ["Fankriss the Unyielding"],
        "count": 1,
        "dkp": 20
    },
    "Battleguard Sartura": {
        "name": ["Battleguard Sartura"],
        "count": 1,
        "dkp": 20
    },
    "Princess Huhuran": {
        "name": ["Princess Huhuran"],
        "count": 1,
        "dkp": 20
    },
    "Viscidus": {
        "name": ["Viscidus"],
        "count": 1,
        "dkp": 20
    },
    "Twin Emperors": {
        "name": ["Emperor Vek'nilash", "Emperor Vek'lor"],
        "count": 2,
        "dkp": 20
    },
    "Ouro": {
        "name": ["Ouro"],
        "count": 1,
        "dkp": 20
    },
    "C'thun": {
        "name": ["C'Thun"],
        "count": 1,
        "dkp": 20
    },
    "Patchwerk": {
        "name": ["Patchwerk"],
        "count": 1,
        "dkp": 40
    },
    "Grobbulus": {
        "name": ["Grobbulus"],
        "count": 1,
        "dkp": 40
    },
    "Thaddius": {
        "name": ["Thaddius"],
        "count": 1,
        "dkp": 40
    },
    "Gluth": {
        "name": ["Gluth"],
        "count": 1,
        "dkp": 40
    },
    "Heigan the Unclean": {
        "name": ["Heigan the Unclean"],
        "count": 1,
        "dkp": 40
    },
    "Noth the Plaguebringer": {
        "name": ["Noth the Plaguebringer"],
        "count": 1,
        "dkp": 40
    },
    "Loatheb": {
        "name": ["Loatheb"],
        "count": 1,
        "dkp": 40
    },
    "Anub'Rekhan": {
        "name": ["Anub'Rekhan"],
        "count": 1,
        "dkp": 40
    },
    "Grand Widow Faerlina": {
        "name": ["Grand Widow Faerlina"],
        "count": 1,
        "dkp": 40
    },
    "Maexxna": {
        "name": ["Maexxna"],
        "count": 1,
        "dkp": 40
    },
    "Instructor Razuvious": {
        "name": ['Instructor Razuvious'],
        "count": 1,
        "dkp": 40
    },
    "Gothik the Harvester": {
        "name": ["Gothik the Harvester"],
        "count": 1,
        "dkp": 40
    },
    "The Four Horsemen": {
        "name": ['Highlord Mograine', "Thane Korth'azz", "Lady Blaumeux", "Sir Zeliek"],
        "count": 4,
        "dkp": 40
    },
    "Sapphiron": {
        "name": ["Sapphiron"],
        "count": 1,
        "dkp": 40
    },
    "Kel'Thuzad": {
        "name": ["Kel'Thuzad"],
        "count": 1,
        "dkp": 40
    },
    "Magtheridon": {
        "name": ["Magtheridon"],
        "count": 1,
        "dkp": 1,
    },
    "High King Maulgar": {
        "name": ["High King Maulgar"],
        "count": 1,
        "dkp": 1,
    },
    "Gruul the Dragonkiller": {
        "name": ["Gruul the Dragonkiller"],
        "count": 1,
        "dkp": 1,
    }
}

class Parser:
    def __init__(self, header, loop, f1, f2, event, chapter_members):
        self.header = header
        self.loop = loop
        self.encounters = []
        self.f1 = f1
        self.f2 = f2
        self.event = event
        self.started = False
        self.chapter_members = chapter_members
        self.eligible_members = []
        self.raid_members = []
        self.connector = aiohttp.TCPConnector(limit=100)
        self.client = aiohttp.ClientSession(connector=self.connector, json_serialize=json.dumps)

        # Build eligible member list
        for member in self.chapter_members:
            name = self.clean_name(member['displayName'])
            self.eligible_members.append(name)

        # Locally track any manually added attendees
        for member in self.event['attendees']:
            self.raid_members.append(member['userDetail']['displayName'])

        print(f"{len(self.eligible_members)} Members eligible for raid:")
        print(self.eligible_members)

        print(f"{len(self.raid_members)} Members currently attending raid:")
        print(self.raid_members)

    # Read the log file from start to end and wait for new lines
    async def live_reader(self):
        f = self.f1
        while True:
            where = f.tell()
            line = f.readline()
            if not line:
                line = await self.loop.run_in_executor(io_pool_exc, f.readline)
                await asyncio.sleep(0)
                continue
            await asyncio.sleep(0)
            if self.started is False:
                await self.parse_initial_members(line)
            await self.find_encounters(where, line)

    # Periodically the event to see if it has started, or for any manual changes
    async def check_event(self):
        
        while True:
            resp = await self.client.get(f"https://www.addictguild.com/api/chapters/0/dkp/0/events/{self.event['slug']}/", headers=self.header)
            self.event = await resp.json()
            if self.event['state'] == 'in_progress':
                self.started = True
            await asyncio.sleep(30)

    # Parse a combat log line and split the timestamp and event.
    def parse_line(self, line):
        # This is in a try block since enchanting a weapon will add another double-space to the log line
        try:
            # two spaces are used to split the date/time field from the actual combat data
            timestamp, event = line.split('  ', 1)
            timestamp = f"{datetime.now().year} {timestamp}"

            timestamp = datetime.strptime(timestamp, '%Y %m/%d %H:%M:%S.%f')
            timestamp = timestamp.astimezone(reference.LocalTimezone())

            event = event.replace('"', '')
            event = event.split(',')
            return timestamp, event
        except:
            print(line)
            return None, None
        

    # Fix naming nonsense
    def clean_name(self, name):
        name = name.replace("-Heartseeker", "") \
                            .replace("ê","e") \
                            .replace("È", "E") \
                            .replace("è", "e") \
                            .replace("é", "e") \
                            .replace("Zelara", "Xel") \
                            .replace("Totemsade", "Rival") \
                            .replace("Srumar", "littlesimpin") \
                            .replace("Holysis", "ragma") \
                            .replace("Aftermath", "Dontpolyme") \
                            .replace("Dontpolymee", "Dontpolyme") \
                            .replace("Weann", "beanhead") \
                            .replace("Stratos", "Krayner") \
                            .replace("Tehbannedbus", "Tehshortbus") \
                            .replace("Itsokikite", "Itso") \
                            .replace("Aelois", "keylen") \
                            .replace("Bayerl", "Romed") \
                            .replace("Notnotmag", "magnite") \
                            .replace("Gandiisdruid", "Gandii") \
                            .replace("Malenh", "Kevlarr")
        return name

    # Look for ENCOUNTER_* lines in the live log
    async def find_encounters(self, where, line):
        
        timestamp, event = self.parse_line(line)

        if timestamp is not None and event is not None:
            if timestamp > parser.parse(self.event['created']):
                if event[0] in ["ENCOUNTER_START"]:
                    print('found encounter_start')
                    await asyncio.sleep(15)
                    self.encounters.append({
                        'type': event[0],
                        'boss': event[2],
                        'log_line': where,
                        'timestamp': timestamp,
                        'group_size': event[4],
                        'processed': False,
                    })
                if event[0] in ["ENCOUNTER_END"]:
                    print('found encounter_end')
                    await asyncio.sleep(15)
                    self.encounters.append({
                        'type': event[0],
                        'boss': event[2],
                        'log_line': where+50000, # add a buffer since the kill can be after the encounter end
                        'timestamp': timestamp,
                        'group_size': event[4],
                        'processed': False,
                    })


    # Periodically check the list of encounters detected in the log file.
    # If an ENCOUNTER_END is found, parse it from start to finish
    async def watch_encounters(self):
        while True:
            for i, encounter in enumerate(self.encounters):
                if encounter['type'] == "ENCOUNTER_END":
                    await self.parse_encounter(self.encounters[i-1], encounter)
                    self.encounters.remove(self.encounters[i-1])
                    self.encounters.remove(encounter)
            await asyncio.sleep(5)

    # Diff current combatants with the raid list
    def diff_add(self, combatants):
        combatants = (combatant.lower() for combatant in combatants)
        raid_members = (member.lower() for member in self.raid_members)
        return list(set(self.clean_combatant_list(combatants)) - set(raid_members))

    def diff_remove(self, combatants):
        combatants = (combatant.lower() for combatant in combatants)
        raid_members = (member.lower() for member in self.raid_members)
        return list(set(raid_members) - set(self.clean_combatant_list(combatants)))

    async def parse_encounter(self, encounter_start, encounter_stop):
        # Something fucked, try to add attendees before the boss kill
        if len(self.raid_members) < 1:
            await self.parse_initial_members(encounter_start['log_line'])

        print(f"Parsing {encounter_start['boss']}")
        kill = False
        kill_timestamp = None
        kill_count = 0
        combatants = []

        f = self.f2
        f.seek(encounter_start['log_line'])

        while True:
            where = f.tell()
            if kill is True:
                print(f"{encounter_start['boss']} encounter successful!")

                # Website API Logic
                if self.started is False:
                    self.started = True
                    await self.start_event()
                    # Start the raid
                # Do Attendance diffing shit
                print('Combatants:')
                print(combatants)
                print(f"Expected length: {encounter_stop['group_size']}, Actual length: {len(combatants)}")
                combatant_remove = self.diff_remove(combatants)
                combatant_add    = self.diff_add(combatants)
                print(f"Remove: {combatant_remove}")
                print(f"Add: {combatant_add}")
                self.raid_members = self.raid_members + combatant_add
                await self.add_attendance(combatant_add)
                # Add the kill
                await self.add_kill(encounter_start['boss'], BOSSES[encounter_start['boss']]['dkp'], kill_timestamp)
                break

            line = f.readline()

            timestamp, event = self.parse_line(line)
            if timestamp is None or event is None:
                break

            # Parse combatant info at start of encounter to get playerGUIDS
            if event[0] == "COMBATANT_INFO":
                combatants.append(event[1])

            # Use every action during the encounter to replace playerGUIDS with actual player names
            if "SPELL_" in event[0]:
                # Once they are all replaced we don't have to run this anymore
                for combatant in combatants:
                    if "Player-" in combatant:
                        combatant = event[2]
                        combatant = self.clean_name(combatant)
                        if event[1] in combatants:
                            combatants.append(combatant)
                            combatants.remove(event[1])

            # Check if the boss died
            if "UNIT_DIED" in event[0]:
                if encounter_start['boss'] in BOSSES:

                    if event[6] in BOSSES[encounter_start['boss']]['name']:                        
                        kill_count += 1
                        if kill_count == BOSSES[encounter_start['boss']]['count']:
                            kill = True                            
                            kill_timestamp = timestamp

            if where > encounter_stop['log_line']:
                print(f"Stopping at line {where}")
                print('Wipe.')
                break

    # This looks at any line before any encounters take place to look for potential attendees
    # and tracks them locally as well as adds them on the website
    async def parse_initial_members(self, line):
        timestamp, event = self.parse_line(line)

        if timestamp is not None and event is not None:

            if "SPELL_" in event[0]:
                combatant = event[2]
                combatant = self.clean_name(combatant)
                
                if self.eligible_member(combatant):
                    if combatant.lower() not in map(str.lower, self.raid_members):
                        self.raid_members.append(combatant)
                        await self.add_attendance([combatant])

    # Is the user an eligible member (IE tagged for chapter)
    def eligible_member(self, combatant):
        if combatant.lower() in map(str.lower, self.eligible_members):
            return True
        else:
            return False

    # Checks a list of combatants for eligibility (IE tagged for chapter)
    def clean_combatant_list(self, combatants):
        clean_combatants = []
        for combatant in combatants:
            if self.eligible_member(combatant):
                clean_combatants.append(combatant)
        return clean_combatants

    # This handles the API request to the website only
    async def add_attendance(self, combatants):
        for combatant in combatants:
            for member in self.chapter_members:
                if combatant.lower() == member['displayName'].lower():
                    print(f'Adding {combatant} to attendee list')
                    data = {"user": member['id'], "standby": False}
                    resp = await self.client.post(f"https://www.addictguild.com/api/chapters/40/dkp/33/events/{self.event['slug']}/attendance/", json=data, headers=self.header)
                    print(resp.status)

    # This handles the API request to the website only        
    async def add_kill(self, boss, dkp, timestamp):
        print('debug: if boss not in event list')
        print(f"BOSS: {boss}")
        print(self.event['entities'])


        if boss not in self.event['entities']:
            print(f'Adding {boss} to website kill list')
            data = {"entity": boss, "dkp": dkp, "created": timestamp.isoformat()}
            resp = await self.client.post(f"https://www.addictguild.com/api/chapters/40/dkp/33/events/{self.event['slug']}/entities/", json=data, headers=self.header)
            print(resp.status)

    # This handles the API request to the website only
    async def start_event(self):
        print("Starting Event.  Way to fail.")
        resp = await self.client.post(f"https://www.addictguild.com/api/chapters/40/dkp/33/events/{self.event['slug']}/start/", headers=self.header)
        print(resp.status)

    def screen_grab(self, rect):
        """ Given a rectangle, return a PIL Image of that part of the screen.
            Handles a Linux installation with and older Pillow by falling-back
            to using XLib """

        x, y, width, height = rect

        image = ImageGrab.grab( bbox=[ x, y, x+width, y+height ] )
        return image

    def clean_awarded_items(self):
        awarded_items = self.event['awardedItems']
        for item in awarded_items:
            try:
                del item['id']
                del item['dkp']
                del item['created']
                del item['event']
                del item['user']
                del item['item']['id']
                del item['item']['slug']
                del item['item']['game']
                del item['userDetail']['username']
                del item['userDetail']['slug']
                del item['userDetail']['avatar']
                del item['userDetail']['rank']
                del item['userDetail']['id']
                del item['sectionSlug']
            except:
                pass # already ran this for this item
        return awarded_items

    async def read_chat(self):
        # Area of screen to monitor
        screen_rect = [
            5,     # x
            1128,   # y
            618,    # width
            275     # height
        ]
        chat_log = []
        purchases = []

        while (True):
            image = self.screen_grab(screen_rect)        # Grab the area of the screen
            ocr_text = pytesseract.image_to_string(image).strip()  # OCR the image

            # add lines to growing chat log
            for text in ocr_text.split("\n"):
                if text not in chat_log:
                    chat_log.append(text.replace("‘", "'"))

            # churn through chat log for purchases and add new ones
            for log in chat_log:
                if log.startswith(f"[R] [{USERNAME}]: [Biddikus] [") and re.search(r"^.*\] sold.*$", log) is not None: # if items aren't parsing it is because of this line after and
                    if {"text": log, "posted": True} not in purchases:
                        print(f"Appending Biddikus log: {log}")
                        purchases.append({"text": log, "posted": False})

            # loop through purchases and do stuff on posted=false purchases
            for purchase in purchases:
                if purchase['posted'] is False:
                    print(f"Processing Purchase: {purchase}")
                    buy = purchase['text'].replace(f"[R] [{USERNAME}]: [Biddikus] ", "")
                
                    try:
                        item = re.search(r"^.*\[(.*)\].*$", buy)
                        if item is None:
                            # fail and mark it complete
                            purchase['posted'] = True
                            print('Failed to item')
                            continue
                        item = item.group(1)
                        user = re.search(r"sold to (.*) for", buy)
                        if user is None:
                            # fail and mark it complete
                            purchase['posted'] = True
                            print('Failed to user')
                            continue
                        user = user.group(1)
                        dkp = re.search(r"for (.*)dkp", buy)
                        if dkp is None:
                            # fail and mark it complete
                            purchase['posted'] = True
                            print('Failed to dkp amount')
                            continue
                        dkp = int(dkp.group(1))
                    except:
                        print('Failed to process log line')
                        continue

                    print(f"Succesfully parsed purchase of {item} by {user} for {dkp} dkp.")

                    check = {
                        "item": {
                            "title": item
                        },
                        "userDetail": {
                            "displayName": user
                        }
                    }

                    awarded_items = self.clean_awarded_items()

                    if check not in awarded_items:
                        # update the local cache of the raid in case the item was manually added
                        resp = await self.client.get(f"https://www.addictguild.com/api/chapters/40/dkp/33/events/{self.event['slug']}/", headers=self.header)
                        self.event = await resp.json()

                    awarded_items = self.clean_awarded_items()

                    if check not in awarded_items:
                        # if the item is still not in the local cache
                        user_id = None
                        for attendee in self.chapter_members:
                            if self.clean_name(attendee['displayName']) == user:
                                print(f"Found {self.clean_name(attendee['displayName'])} is purchaser of [{item}]")
                                user_id = attendee['id']

                        data = {
                            "user": user_id,
                            "item": item,
                            "dkp": dkp
                        }
                        # if we got a user id from the attendees try a post
                        if user_id is not None:
                            resp = await self.client.post(f"https://www.addictguild.com/api/chapters/40/dkp/33/events/{self.event['slug']}/items/", headers=self.header, json=data)
                            print(f"Added [{item}] purchase to {user} for {dkp}dkp.")
                        else:
                            print(f"Failed to add buy for {user}")
                        purchase['posted'] = True
                        
            await asyncio.sleep(15)

def main():
    data = {"username": USERNAME, "password": PASSWORD}
    resp = requests.post('https://www.addictguild.com/api/auth/token/', json=data)

    try:
        token = resp.json()['token']
        header = {'Authorization': f"Token {token}"}
    except:
        print(resp.status_code, resp.reason)
        exit

    resp = requests.get('https://www.addictguild.com/api/chapters/40/dkp/tbc-25-man/active-events/', headers=header)

    print("Active Events:")

    for i, event in enumerate(resp.json()):
        print(f"[{i}] {event['title']}")

    selection = int(input('Select event number: '))

    event = resp.json()[selection]

    print(f"{event['title']} selected.")

    resp = requests.get('https://www.addictguild.com/api/chapters/40/members/', headers=header)

    chapter_members = []
    for member in resp.json():
        if member['leaveDate'] is None:
            chapter_members.append(member['member'])

    ocr = input('Do you want to enable OCR? [y/n]')

    loop = asyncio.get_event_loop()
    list_of_files = glob.glob("C:\\Program Files (x86)\\World of Warcraft\\_classic_\\Logs\\WoWCombatLog*")
    logfile = max(list_of_files, key=os.path.getctime)
    print(logfile)

    # logfile = r"C:\Program Files (x86)\World of Warcraft\_classic_\Logs\WoWCombatLog-052521_172926.txt"
    f1 = open(logfile, encoding='utf-8')
    f2 = open(logfile, encoding='utf-8')
    parser = Parser(header, loop, f1, f2, event, chapter_members)

    loop.create_task(parser.live_reader())
    loop.create_task(parser.watch_encounters())
    loop.create_task(parser.check_event())
    if ocr == 'y':
        loop.create_task(parser.read_chat())
    print('starting loop')
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Shutting down..")
        loop.stop()
    finally:
        loop.close()        


if __name__ == "__main__":
    main()