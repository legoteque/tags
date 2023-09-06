import os, json, time, re, datetime
import pandas as pd
pd.set_option('display.max_columns', None)
from urllib.parse import unquote
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4FreeForm
import xml.etree.ElementTree as ET

import spotipy
from spotipy.oauth2 import SpotifyOAuth

#spotify
USERNAME = "legoteque"
CID = "9741495b11f1423aa513f2c7ef382924"
SECRET = "0d56b6bcbe624ee094c856ab8cc72876"
SCOPE = "playlist-modify-public"
URI = "http://localhost"

# Set environment variables
os.environ['SPOTIPY_CLIENT_ID'] = '9741495b11f1423aa513f2c7ef382924'
os.environ['SPOTIPY_CLIENT_SECRET'] = '0d56b6bcbe624ee094c856ab8cc72876'
os.environ['SPOTIPY_REDIRECT_URI'] = "http://localhost"

SP = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))

#mutagen
UTF8 = mutagen.id3.Encoding.UTF8
LATIN1 = mutagen.id3.Encoding.LATIN1

#registro tags que no són a EasyID3
EasyID3.RegisterTextKey("comments", "COMM::eng")
EasyID3.RegisterTextKey("group", "GRP1")
EasyID3.RegisterTextKey("key", "TKEY")



with open('data.json') as json_file:
    data = json.load(json_file)
    
TAGMAPID3 = data["TAGMAPID3"]
TAGMAPMP4 = data["TAGMAPMP4"]
ITUNES_DATA = data["ITUNES_DATA"]

#setup iTunes
PATH = ITUNES_DATA["PATH"]
MAC_MUSIC_PATH = "file:///Users/legoteque"
USER = ITUNES_DATA["USER"]
PASS = ITUNES_DATA["PASS"]
ITUNES_FOLDER = ITUNES_DATA["ITUNES_FOLDER"]
ITUNES_MUSIC_FOLDER = ITUNES_DATA["ITUNES_MUSIC_FOLDER"]
ITUNES_XML_FILE = ITUNES_DATA["ITUNES_XML_FILE"]
MY_ITUNES_TAGS = ITUNES_DATA["MY_ITUNES_TAGS"]

ITUNES_XML_PATHFILE = PATH + os.sep + ITUNES_FOLDER + os.sep + ITUNES_XML_FILE
ITUNES_MUSIC_PATH = PATH + os.sep + ITUNES_MUSIC_FOLDER

PC_SHARING_FOLDER = "D:\MUSIQUE\PASAR A MAC"

MAC_REMOTEWIN_REPLACE = {"/Music/": "/Musica/",
                         MAC_MUSIC_PATH: PATH,
                         "/": "\\",
                         "\"": '\uf020',
                         "*": "\uf021",
                         "<": "\uf023",
                         ">": "\uf024",
                         "?": "\uf025",
                         "|": "\uf027"}




#converteix milisegons a 'h:mm:ss'
def ms_to_string(time, metric="miliseconds"):
    if metric == "miliseconds": s = round(int(time) / 1000)
    elif metric == "seconds": s = int(time)
    td = datetime.timedelta(seconds=s)
    string = str(td)
    string_l = string.split(":")[-3:]
    string_l[-3] = string_l[-3].lstrip("0")
    if string_l[-3] == "": string_l = string_l[-2:]
    string_l[-2] = string_l[-2].lstrip("0")
    if string_l[-2] == "": string_l[-2] = "0"
    string = ":".join(string_l)
    return string



#Audio files list in path
def audio_files_in_folder(path, subfolders=False):
    audio_ext = (".mp3", ".m4a")
    audio_l = []
    if subfolders:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(audio_ext):
                    audio_l.append(root + os.sep + file)
    else:
        files_l = list(os.scandir(path))
        for element in files_l:
            if element.is_file() & element.name.endswith(audio_ext):
                audio_l.append(path + os.sep + element.name)
    return audio_l

#establim una conexio amb un path remot
def connection_to_host(path, user, password):
    print(f"Iniciant conexió amb {path}")
    mount_command = "net use /user:" + user + " " + path + " " + password
    os.system(mount_command)
    
#funcio que aturara i treura missatge si no hi ha conexio a l'xml remot i si la hi ha retorna l'ultima modificacio
def remote_xml_conected_assert():
    connection_to_host(PATH, USER, PASS)
    assert os.path.isdir(PATH + os.sep + ITUNES_FOLDER), f"No s'obten resposta de {PATH}"
    print(f"Conexió amb {PATH} establerta")
    assert os.path.isfile(ITUNES_XML_PATHFILE), f"\nNo es troba '{ITUNES_XML_FILE}' a '{ITUNES_FOLDER}'"
    return time.ctime(os.path.getmtime(ITUNES_XML_PATHFILE))
        
    
        
class ItunesLibrary:
    def __init__(self, xml_local_path=None, max_tracks_pl=2000):
        self.mytags = MY_ITUNES_TAGS
        
        if xml_local_path == None:
            self.xml_path = ITUNES_XML_PATHFILE
            remote_xml_conected_assert()
        else:
            self.xml_path = xml_local_path
        
        self._read_xml_file() 
        self._tracks_df_from_xml()
        self._duplicated()
        self._read_playlists(max_tracks=max_tracks_pl)
        

#INIT CLASS   
    def _read_xml_file(self):
        print(f"\nLlegint '{ITUNES_XML_FILE}'")
        tree = ET.parse(self.xml_path)
        dicts = tree.findall("dict")
        self.element_tracks = list(dicts[0])[17]
        self.element_playlists = list(list(dicts[0])[19])
        self._dict_elem_l = self.element_tracks.findall("dict")
        print(f"Elements de tracks del XML carregats a .element_tracks'")
        
    #treu tots els tags de tots els tracks en un dataframe
    def _tracks_df_from_xml(self):
        print("\nGenerant dataframe amb la informació dels tracks de la biblioteca d'iTunes")
        lista=[]
        for element in self._dict_elem_l:
            element_dict = {}
            for tag, i in zip(list(element), range(len(element))):
                if i % 2 == 0: key = tag.text
                else: element_dict[key] = tag.text
            lista.append(element_dict)

        tracks_df = pd.DataFrame(lista)[MY_ITUNES_TAGS]
        #esborrem els tracks que no son 'File'
        index = tracks_df[tracks_df["Track Type"] != 'File'].index
        tracks_df.drop(index=index, inplace=True)
        #formategem la columna de duracio a string
        tracks_df["Duration"] = tracks_df["Total Time"].apply(ms_to_string)
        tracks_df["Creation"] = tracks_df["Date Added"]
        #afegim columna d'accés remot als arxius
        def create_remote_location(location):
            rem_loc = unquote(location)
            for k, v in MAC_REMOTEWIN_REPLACE.items():
                rem_loc = rem_loc.replace(k, v)
            return rem_loc
        tracks_df["mac_pc_loc"] = tracks_df.Location.apply(create_remote_location)
        tracks_df["mac_loc"] = tracks_df.Location
        tracks_df["Location"] = tracks_df["mac_pc_loc"] #ubicacio desde pc
        tracks_df["Codec"] = tracks_df.mac_loc.apply(lambda x: "MP3" if x.split(".")[-1].lower() == "mp3" else "AAC")
        tracks_df["color"] = "black"
        tracks_df["linkable"], tracks_df["linked"], tracks_df["level"] = False, False, -1
        tracks_df.fillna("", inplace=True)
        self.msg = f"{len(tracks_df)} tracks a la biblioteca d'iTunes"
        print(f"{len(tracks_df)} tracks insertats a .tracks_df")
        tracks_df.reset_index(drop=True, inplace=True)
        self.tracks_df = tracks_df
    
    #busca ubicacions i combinacions [Artist, Name] duplicats a la llibreria
    def _duplicated(self):
        print("\nBuscant entrades amb la mateixa 'mac_loc' a la biblioteca")
        locations_counts_s = self.tracks_df.mac_loc.value_counts()
        locations = locations_counts_s[locations_counts_s != 1].index
        if len(locations) == 0:
            self.hay_duplicated_locs = False
            msg = "No s'ha trobat cap localització en més d'un track a la biblioteca"
            self.msg += "\n\n" + msg
        else:
            self.hay_duplicated_locs = True
            self.duplicated_locs = self.tracks_df[self.tracks_df.mac_loc.isin(locations)]
            msg = f"{len(self.duplicated_locs.mac_loc.unique())} 'mac_loc' en més d'un track a la biblioteca"
            self.msg += "\n\n" + msg
            print("Creat l'atribut .duplicated_locs per consultar els tracks en qüestió")
            
        print("\nCercant tracks duplicats per [Artist, Name] a la biblioteca")
        finder_df = pd.DataFrame()
        finder_df["Artist"] = self.tracks_df.Artist.str.lower()
        finder_df["Name"] = self.tracks_df.Name.str.lower()
        duplicated_tracks = finder_df[finder_df.duplicated(["Artist", "Name"])]
        if len(duplicated_tracks) != 0:
            self.hay_duplicated_tracks = True
            msg = f"S'han trobat {len(duplicated_tracks)} tracks duplicats a la llibreria d'iTunes."
            self.msg += "\n\n" + msg
            self.duplicated_tracks = duplicated_tracks
            print("S'ha generat l'atribut .duplicated_tracks per consultar els tracks en qüestió.")
        else:
            self.hay_duplicated_tracks = False
            msg = "No hi ha cap track duplicat a la llibreria d'iTunes"
            self.msg += "\n\n" + msg
            
    #read playlists
    def _read_playlists(self, max_tracks):
        print("\nGenerant dataframe amb les playlists de la biblioteca d'iTunes")
        self._folders = {}
        df = pd.DataFrame()
        tracks_pl = {}
        for i in range(len(self.element_playlists)):
            playlist = self.element_playlists[i]
            #if playlist.find("key").text == 'Playlist ID':
            tracks_pl[i] = self._read_tracks_ids(playlist)
            length = len(tracks_pl[i])
            #df = df.append(self._read_playlist_info(playlist, i, length, max_tracks=max_tracks))
            df = pd.concat([df, self._read_playlist_info(playlist, i, length, max_tracks=max_tracks)])
        #esborrem les llistes vuides
        index = df[df.Length == 0].index
        playlists_df = df.drop(index=index)
        #mantenim del diccionari aquelles llistes que estan a playlists_df
        playlists_tracks_dic = {k: tracks_pl[k] for k in playlists_df.index}
        
        #retorna el dataframe donat l'index de la playlist
        def create_playlist_df(num):
            df = pd.DataFrame(data=playlists_tracks_dic[num], columns=["Track ID"])
            df["Position"] = df.index
            df.index = [num] * len(df)
            return pd.concat([playlists_df.loc[[num]], df], axis=1)
        
        all_playlist_songs = pd.DataFrame()
        for i in playlists_tracks_dic.keys():
            #all_playlist_songs = all_playlist_songs.append(create_playlist_df(i))
            all_playlist_songs = pd.concat([all_playlist_songs, create_playlist_df(i)])
        num_playlists = len(playlists_df)
        num_songs_playlists = len(all_playlist_songs)
        
        keep_cols = ['Track ID', 'Artist', 'Name', 'Location', 'Date Modified']
        drop_cols = [col for col in self.mytags if col not in keep_cols]
        tracks_df = self.tracks_df.drop(columns=drop_cols)
        self.playlists_df = pd.merge(all_playlist_songs, tracks_df, on="Track ID", how="left")
        self.playlists_df.drop(columns="Track ID", inplace=True)
        self.playlists_df.reset_index(drop=True, inplace=True)
        
        print(f"{num_songs_playlists} tracks a les {num_playlists} playlists afegides a .playlists_df")

#UTILITATS
    #Find incoherences between Remote Location and remote acces to file with python
    def check_all_remote_locations(self):
        incoherences = []
        div = len(self.tracks_df) // 100
        for rem_loc, i in zip(self.tracks_df["mac_pc_loc"].values.tolist(), range(len(self.tracks_df))):
            if i % div == 0: print(f"Processant: {i // div}%", end='\r')
            if not os.path.isfile(rem_loc):
                incoherences.append(rem_loc)
        if len(incoherences) == 0: print("Totes les 'Remote Locations' s'han pogut ubicar remotament")
        else: 
            print(f"S'han trobat {len(incoherences)} 'Remote Locations' sense poder ubicar remotament")
            self.incoherences = incoherences
            print("S'ha creat l'atribut .incoherences amb les 'Remote Locations' sense localitzar")
            
    #Search by query
    def search(self, query, create_playlist=False):
        #Series for global queries
        indexed_tracks = (self.tracks_df["Name"] + self.tracks_df["Artist"] + self.tracks_df["Composer"] + 
                  self.tracks_df["Album"] + self.tracks_df["Genre"] + self.tracks_df["Comments"])
        indexed_tracks = indexed_tracks.str.lower()
        
        query = query.lower()
        query_l = query.split(sep=" ")
        index = indexed_tracks.apply(lambda value: all(x in value for x in query_l))
        df = self.tracks_df[index]
        if create_playlist == True: self.create_playlist_from_df(df, query)
        return df

    #crea playlist de dataframe a la carpeta compartida del pc
    def create_playlist_from_df(self, df, name):
        filepath_pl = PC_SHARING_FOLDER + os.sep + "playlists" + os.sep + name + ".m3u8"
        with open(filepath_pl, "w") as text_file:
            text_file.write("\n".join(df.Location.values.tolist()))
        print(f"Afegida a '{filepath_pl}' la playlist '{name}'")
    
    #mostra el nombre d'arxius d'audio i sessions a Itunes Media i agrega les localitzacions a listes
    def number_of_audio_and_session_files(self):
        print(f"\nRecopilant a .audio_files_l els arxius d'audio a '{ITUNES_MUSIC_FOLDER}'")
        self.audio_files_l = audio_files_in_folder(ITUNES_MUSIC_PATH)
        songs_num = len(self.audio_files_l)
        print(f"{songs_num} arxius d'audio (mp3 i aac) a la carpeta '{ITUNES_MUSIC_FOLDER}'")
        if len(self.tracks_df) == songs_num: print(f"Coincidència de nombre de tracks a la biblioteca i arxius a '{ITUNES_MUSIC_FOLDER}'")
        else: print(f"¡¡¡No coincideixen el nombre de tracks a la biblioteca i arxius a '{ITUNES_MUSIC_FOLDER}'!!!")
        
        sesions_folder = ITUNES_MUSIC_FOLDER + os.sep + "SESSIONS"
        print(f"\nRecopilant a .sesions_files_l els arxius de sessions a '{sesions_folder}'")
        self.sesions_files_l = audio_files_in_folder(PATH + os.sep + sesions_folder)
        print(f"{len(self.sesions_files_l)} arxius de sessions a la carpeta '{sesions_folder}'")

#FUNCIONS INTERNES        
    #retorna en un dataframe la info de les playlists indexades per parametre
    def _read_playlist_info(self, playlist, index, length, max_tracks):
        playlist = [element.text for element in list(playlist)]
        name_i = playlist.index("Name")
        name_text = playlist[name_i+1]
        is_folder = "Folder" in playlist
        is_smart = "Smart Info" in playlist
        if is_folder:
            folder_id_i = playlist.index("Playlist Persistent ID") + 1
            folder_id = playlist[folder_id_i]
            self._folders[folder_id] = name_text
            return
        else:
            if length > max_tracks: return
            if "Parent Persistent ID" in playlist:
                folder_id_i = playlist.index("Parent Persistent ID") + 1
                folder_id = playlist[folder_id_i]
                folder = self._folders[folder_id]
            else: folder = "root"
            cols = ["Folder", "List", "Smart", "Length"]
            data = [[folder, name_text, is_smart, length]]
            playlist_info_df = pd.DataFrame(index=[index], columns=cols, data=data)
        return playlist_info_df
    
    #retorna llistes amb els tracks ids dels playlists
    def _read_tracks_ids(self, playlist):
        tracks_ids_l = []
        try: 
            tracks_els = list(playlist.findall("array")[0])
            for element in tracks_els:
                tracks_ids_l.append(element.find("integer").text)
        except: None
        return tracks_ids_l

#ALTRES FUNCIONS (en desus)
    def _track_map(self, track_elem_num):
        track = list(self._dict_elem_l[track_elem_num])
        tags_map = {}
        for element, i in zip(track, range(len(track))):
            if i % 2 == 0: value = element.text
            elif value in self.mytags:
                tags_map[value] = i
        return tags_map
    
    #llegeix un valor concret donat el track_elem_num i el tag
    def _read_tag(self, track_elem_num, tag):
        return list(self._dict_elem_l[track_elem_num])[self._track_map(track_elem_num)[tag]].text
    #crea dicionari amb els elements dels mytags del track
    
    #escriure al xml i al dataframe (no serveix de res, a no ser que volguéssim engañar als altres softwares que importen itunes)
    def _write_tag(self, track_elem_num, tag, value):
        self._dict_elem_l[track_elem_num][self._track_map(track_elem_num)[tag]].text = value
        self.tracks_df.loc[track_elem_num, tag] = value
        #falta save xml

    #Retorna el tag (string) o tags (llista) en un string o en un diccionari resptectivament
    def read_tags(self, track_elem_num, tags):
        if type(tags) == str:
            return self._read_tag(track_elem_num, tags)
        elif type(tags) == list:
            results = {}
            for tag in tags:
                results[tag] = self._read_tag(track_elem_num, tag)
            return results

        
            
class AudioFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self._new_values = {}
        if filepath.endswith(".mp3"): 
            self.codec = "MP3"
            self.mytags = list(TAGMAPID3.keys())
        elif filepath.endswith(".m4a"): 
            self.codec = "AAC"
            self.mytags = list(TAGMAPMP4.keys())

        self._load_fileinfo()
        self._load_metadata()
        self._read_tags()
        
#INIT CLASS   
    def _load_fileinfo(self):
        file_info = os.stat(self.filepath)
        times = [file_info.st_mtime, file_info.st_ctime]
        names = ["modification", "creation"]

        for sec, name in zip(times, names):
            date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sec))
            self.__dict__[name] = date
            
        audio = mutagen.File(self.filepath)
        self.__dict__["duration"] = ms_to_string(audio.info.length * 1000)
   
    #instància objecte EasyID3 y mp4
    def _load_metadata(self): 
        if self.codec == "MP3":
            #esborra altres comentaris abans de llegir
            self._del_other_comments()
            self.id3 = EasyID3(self.filepath)
            
        elif self.codec == "AAC":
            self.mp4 = mutagen.File(self.filepath)
    
    #importa dades de EasyID3 o mp4 a variables self.tag i series self.tags
    def _read_tags(self):
        self.tags = pd.Series(data="", index=self.mytags, dtype="object")

        if self.codec == "MP3":
            for tag in self.mytags:
                if tag in self.id3.keys():
                    self.tags[tag] = "[void]".join(self.id3[tag])
                    # self.tags[tag] = self.id3[tag][0]
                self.__dict__[tag] = self.tags[tag]
            #copia el valor de group a grouping despres de llegir la data
            self._group_to_grouping()
            
                    
        elif self.codec == "AAC":
            for tag in self.mytags:
                tag_code = TAGMAPMP4[tag]
                if tag_code in self.mp4.keys():
                    if tag == "tracknumber": self.tags[tag] = str(self.mp4[tag_code][0][0])
                    elif tag == "key": self.tags[tag] = self.mp4[TAGMAPMP4["key"]][0].decode()
                    # else: self.tags[tag] = str(self.mp4[tag_code][0])
                    else: self.tags[tag] = str(self.mp4[tag_code][0]).replace("\x00", "[void]")
                self.__dict__[tag] = self.tags[tag]
            #afegim isrc del label
            if self.label != "": 
                label_l = self.label.split(":")
                self.isrc = label_l[-1]
            else: self.isrc = ""
                
#FUNCIONS INTERNES        
    def _add_mp3_comment(self):
        audio = mutagen.File(self.filepath)
        audio.tags.add(mutagen.id3.COMM(name="COMM::eng", text=["[void]"], encoding=UTF8, lang="eng", desc=''))
        audio.save()
        self.id3 = EasyID3(self.filepath)
    
    #Omple self._new_values i, per defecte, retorna False si hi ha valors nous
    def _check_new_values(self):
        
        for tag, value in self.tags.items():
            if value != self.__dict__[tag]:
                self._new_values[tag] = self.__dict__[tag]
        if not bool(self._new_values): return False
        
        #formategem els tags especials a self._new_values
        if self.codec == "MP3":
            #crea el tag de comentari si no existeix
            if ("comments" in self._new_values.keys()) & (self.tags["comments"] == ""):
                self._add_mp3_comment()
            numeric = ["bpm", "tracknumber", "date"]
            for k, v in self._new_values.items():
                if (k in numeric) & (v == ""): self._new_values[k] = "0"
                elif k == "genre":
                    if v == "": self._new_values[k] = "None"
                    else: self._new_values[k] = v
                elif v == "": self._new_values[k] = "[void]" #abans "\X00" però hi habia problemes amb la invisiblitat d'aquest caracter a itunes
        elif self.codec == "AAC": 
            for k, v in self._new_values.items():
                if k == "bpm":
                    if v == "": self._new_values[k] = 0
                    else: self._new_values[k] = int(v)
                elif k == "tracknumber":
                    if v == "": self._new_values[k] = (0, 0)
                    else: self._new_values[k] = (int(v), 0)
                elif k == "key":
                    if v == "": self._new_values[k] = MP4FreeForm("\0".encode('UTF-8'), mutagen.mp4.AtomDataType.UTF8)
                    else: self._new_values[k] = mutagen.mp4.MP4FreeForm(v.encode('UTF-8'), mutagen.mp4.AtomDataType.UTF8)
                elif k == "date":
                    if v == "": self._new_values[k] = "0001"
                elif v == "": self._new_values[k] = "[void]"
        return True
      
    #borra tb el valor de grouping i autotags serato i altres tags de comments
    def _del_other_comments(self):
        audio = mutagen.File(self.filepath)
        keys = [key for key in audio.keys() if ("COMM" in key) & (key != "COMM::eng")]
        for key in keys: del audio[key]
        audio.save()
    
    def _group_to_grouping(self):
        if self.group == "": new_value = "\0"
        else: new_value = self.group
            
        audio = mutagen.File(self.filepath)
        audio.tags.add(mutagen.id3.TIT1(text=[new_value], encoding=LATIN1))
        audio.save()
            
#UTILITATS
    def save(self, save=True, show_before=False, show_after=False):
        if not self._check_new_values(): 
            print("no hi ha valors nous")
            return False
            
        if self.codec == "MP3":               
            for key, new_value in self._new_values.items():
                self.id3[key] = [new_value]
            if save: self.id3.save()
            
        elif self.codec == "AAC":
            for key, new_value in self._new_values.items():
                self.mp4[TAGMAPMP4[key]] = [new_value]     
            if save: self.mp4.save()
        
        self._new_values = {}
        self._load_metadata()
        #self._load_fileinfo()
        
        if show_before: print(self.tags)
        self._read_tags()
        if show_after: print(self.tags)
        
        return True
       
    #extreu dataframe de info i de self.tags (no modificables fins save())
    def data_df(self):
        keys = ["filepath", "codec", "modification", "creation", "duration"]
        values = [self.filepath, self.codec, self.modification, self.creation, self.duration]
        info = dict(zip(keys, values))
        info = pd.DataFrame(data=info, index=[0])
        tags = pd.DataFrame(data=dict(self.tags), index=[0])
        return pd.concat([info, tags], axis=1)
            
    def del_mytags(self, save=True, show_before=False, show_after=False):
        for tag in self.mytags:
            self.__dict__[tag] = ""
        self.save(save=save, show_before=show_before, show_after=show_after)   



class Spotify:
    def __init__(self, filename):
        self.audio = AudioFile(filename)
        self.artist = artist = self.audio.artist
        self.title = title = self.audio.title
        
        query = artist.split(";")[0] + " " + title
        self.track_results = self._search(query, limit=10)
        self.top_tracks = None
        
        self._check_has_id()

        #all_genres = SP.recommendation_genre_seeds()["genres"]
    
    def _check_has_id(self):
        if len(self.audio.spotify) != 22: 
            self.has_id = False
            self.id = None
            self.artist_id = None
        else: 
            self.has_id = True
            self.id = self.audio.spotify
            self.artist_id = SP.track(self.id)["artists"][0]["id"]
            self._find_artist_top_tracks()
        
    def set_id(self, index):
        id = self.track_results.loc[index, "id"]
        self.audio.spotify = id
        self.audio.save()
        self._check_has_id()
       
    def _search(self, query, limit):
        data = SP.search(query, limit=limit)
        founded = data['tracks']["items"]
        founded_df = self._build_info_df(founded)
        founded_df.sort_values(by="popularity", ascending=False, inplace=True)
        founded_df.reset_index(drop=True, inplace=True)
        return founded_df.head()
    
    def _find_artist_top_tracks(self):
        top = SP.artist_top_tracks(self.artist_id)['tracks']
        top_df = self.build_info_df(top)
        top_df.sort_values(by="popularity", ascending=False, inplace=True)
        top_df.reset_index(drop=True, inplace=True)
        self.top_tracks = top_df.head()

    def _build_info_series(self, track):
        track_s = pd.Series(dtype="object")
        track_s["id"] = track["id"]
        track_s["artists"] = ";".join([artist["name"] for artist in track["artists"]])
        track_s["main artist id"] = track["artists"][0]['id']
        track_s["main artist url"] = track["artists"][0]['external_urls']['spotify']
        track_s["name"] = track["name"]
        track_s["track url"] = track["external_urls"]['spotify']
        track_s["year"] = track["album"]["release_date"][:4]
        track_s["album"] = track["album"]["name"]
        track_s["album_type"] = track["album"]["album_type"]
        seconds = track["duration_ms"] / 1000
        track_s["duration"] = f"{int(seconds // 60)}:{str(int(seconds % 60)).zfill(2)}"
        track_s["seconds"] = seconds
        track_s["explicit"] = track["explicit"]
        track_s["popularity"] = track["popularity"]
        track_s["isrc"] = track["external_ids"]["isrc"]
        return track_s

    def _build_info_df(self, tracks_l):
        tracks_df = pd.DataFrame()
        for i in range(len(tracks_l)):
            data = self._build_info_series(tracks_l[i])
            tracks_df = tracks_df.append(pd.DataFrame(data).T)
        return tracks_df.reset_index(drop=True)

    def _return_ids(self, tracks_l):
        ids = []
        for track in data:
            ids.append(track["id"])
        return ids

    def _obtain_features(self, ids):
        data = SP.audio_features(ids)
        features_df = pd.DataFrame()
        for track in data:
            features = pd.DataFrame(pd.Series(data[0])).T
            features_df = features_df.append(features)
        features_df.reset_index(drop=True, inplace=True)
        index = features_df.columns.str.contains("uri|url|href")
        return features_df.drop(columns=features_df.columns[index])

    def _recommendations(self, ids_l):
        data = SP.recommendations(seed_tracks=ids_l, limit=20)
        recomended = data["tracks"]
        return build_info_df(recomended)

    def _features(self, id):
        SP.audio_features([id])