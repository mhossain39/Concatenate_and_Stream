#!/usr/bin/env python3

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst, GLib
Gst.init(None)
gi.require_version('GstPbutils', '1.0')
from gi.repository.GstPbutils import Discoverer
class MediaInfo:

 def __init__(self, source):
    """
    Check a media source as a valid file or uri and return the proper uri
    """


    src_info = self.source_info(source)
    self.uri = ''
    self.result = dict()
    
    if src_info['is_file']:  # Is this a file?
        self.uri = src_info['uri']

    elif Gst.Uri.is_valid(source):  # Is this a valid URI source for Gstreamer
        uri_protocol = Gst.uri_get_protocol(source)
        if Gst.Uri.protocol_is_supported(Gst.URIType.SRC, uri_protocol):
            self.uri = source
    if self.uri:
        self.get_media_uri_info(self.uri)
    else:
        print ("Invalid URI")


 def time_to_string(self, value):

    """
    Converts the given time in nanoseconds to a human readable string
    Format HH:MM:SS.XXX
    """
    if value == Gst.CLOCK_TIME_NONE:
        return "--:--:--.---"
    ms = value / Gst.MSECOND
    sec = ms / 1000
    ms = ms % 1000
    mins = sec / 60
    sec = sec % 60
    hours = mins / 60
    mins = mins % 60
    return "%01d:%02d:%02d.%03d" % (hours, mins, sec, ms)


 def beautify_length(self, length):
    """
    Converts the given time in nanoseconds to a human readable string
    """
    sec = length / Gst.SECOND
    mins = int(sec / 60)
    sec = int(sec % 60)
    hours = int(mins / 60)
    mins = int(mins % 60)

    parts = []
    if hours:
        parts.append(ngettext("%d hour", "%d hours", hours) % hours)

    if mins:
        parts.append(ngettext("%d minute", "%d minutes", mins) % mins)

    if not hours and sec:
        parts.append(ngettext("%d second", "%d seconds", sec) % sec)

    return ", ".join(parts)
 def path2uri(self, path):
    """
    Return a valid uri (file scheme) from absolute path name of a file

    >>> path2uri('/home/john/my_file.wav')
    'file:///home/john/my_file.wav'

    >>> path2uri('C:\Windows\my_file.wav')
    'file:///C%3A%5CWindows%5Cmy_file.wav'
    """
    try: # py3 version
        from urllib.parse import urljoin
        from urllib.request import pathname2url
    except: #py2 version
        from urlparse import urljoin
        from urllib import pathname2url

    return urljoin('file:', pathname2url(path))


 def source_info(self, source):
    import os.path

    src_info = {'is_file': False, 'uri': '', 'pathname': ''}

    if os.path.exists(source):
        src_info['is_file'] = True
        # get the absolute path
        src_info['pathname'] = os.path.abspath(source)
        # and make a uri of it
        src_info['uri'] = self.path2uri(src_info['pathname'])
    return src_info




 def tag_reader(self, li, tag, data):
    if tag == 'audio-codec' or tag == 'video-codec'  or tag == 'encoder' 'container-format' :
       data[tag] = li.get_string(tag)[1]

 def get_media_uri_info(self, uri):

    GST_DISCOVER_TIMEOUT = 5000000000
    uri_discoverer = Discoverer.new(GST_DISCOVER_TIMEOUT)
    try:
        uri_info = uri_discoverer.discover_uri(uri)
    except GLib.GError as e:
        return False


    # Duration in seconds
    self.result['duration'] = self.time_to_string(uri_info.get_duration() / Gst.NSECOND)
    self.result['seconds'] = uri_info.get_duration() / Gst.SECOND
    self.result['seekable'] = uri_info.get_seekable()
    self.result['audio-streams'] = []
    self.result['video-streams'] = []
    tags = uri_info.get_tags()
    audio_streams = uri_info.get_audio_streams()
    video_streams = uri_info.get_video_streams()
    self.result['audio-codec'] = ''
    self.result['video-codec'] = ''
    tags.foreach(self.tag_reader,self.result)

    for stream in video_streams:
        st = stream.get_caps().get_structure(0)
        stream_info = {'bitrate': stream.get_bitrate(),
                       'framerate': stream.get_framerate_num(),
                       'depth': stream.get_depth(),
                       'max_bitrate': stream.get_max_bitrate(),
                       'width': stream.get_width(),
                       'height': stream.get_height(),
                       'profile': st.get_value("profile")

                       }
        self.result['video-streams'].append(stream_info)

    for stream in audio_streams:

        stream_info = {'bitrate': stream.get_bitrate(),
                       'channels': stream.get_channels(),
                       'depth': stream.get_depth(),
                       'max_bitrate': stream.get_max_bitrate(),
                       'samplerate': stream.get_sample_rate(),
                       'caps': stream.get_caps().to_string()
                       }
        self.result['audio-streams'].append(stream_info)


#info = MediaInfo("/home/improsys/momenthouse/b0.mp4")

#if (info.result):

#  print(info.result)
