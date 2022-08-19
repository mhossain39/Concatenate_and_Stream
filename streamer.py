import gi
import sys, os, time
from datetime import datetime
import platform
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GLib
os.environ["G_DEBUG"] = "all"
os.environ["G_MESSAGES_DEBUG"] = "all"
os.environ["GTK_DEBUG"] = "all"
os.environ["GST_DEBUG"] = "0"
os.environ["python"] = "5"
import glob
#GObject.threads_init()
Gst.init(None)
from media_info import MediaInfo
class Streamer:
	def __init__(self, temp_file_list, rtmp_urls):
		self.file_to_stream = ''
		self.file_list = []
		width=0
		height=0
		vcodec=''
		acodec=''
		profile=''
		for f in temp_file_list:
			info = MediaInfo(f)
			if info.result:
				if width==0 and height==0 and vcodec == '':
					width=info.result['video-streams'][0]['width']
					height=info.result['video-streams'][0]['height']
					vcodec=info.result['video-codec']
					acodec=info.result['audio-codec']
					profile=info.result['video-streams'][0]['profile']				
					self.file_list.append(f)
				elif width==info.result['video-streams'][0]['width'] and height==info.result['video-streams'][0]['height'] and vcodec==info.result['video-codec'] and profile==info.result['video-streams'][0]['profile']:
					self.file_list.append(f)
		self.last_pts = 0
		self.mainloop = GLib.MainLoop()
		self.pipeline =   Gst.Pipeline()
		self.bus = self.pipeline.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect('message::eos', self.on_eos)
		self.bus.connect('message::error', self.on_error)
		self.bus.connect('message', self.on_message)
		self.src = Gst.ElementFactory.make('souphttpsrc', None)
		self.demuxer = Gst.ElementFactory.make('qtdemux', None)
		self.q1 = Gst.ElementFactory.make('queue', None)
		self.q2 = Gst.ElementFactory.make('queue', None)

		self.tee = Gst.ElementFactory.make('tee', None)
		self.vparse = Gst.ElementFactory.make('h264parse', None)
		self.aparse = Gst.ElementFactory.make('aacparse', None)
		self.mux = Gst.ElementFactory.make('flvmux', None)
		self.mux.set_property('streamable',True)
		self.mux.set_property('start-time-selection',2)


		self.pipeline.add(self.src)
		self.pipeline.add(self.demuxer)
		self.pipeline.add(self.vparse)
		self.pipeline.add(self.aparse)
		self.pipeline.add(self.q1)
		self.pipeline.add(self.q2)
		self.pipeline.add(self.tee)
		self.pipeline.add(self.mux)

		self.demuxer.connect("pad-added", self.demuxer_callback)
		self.src.link(self.demuxer)
		self.mux.link(self.tee)
		for count, value in enumerate(rtmp_urls):
			setattr(self,'qt'+str(count),Gst.ElementFactory.make('queue', None))
			q = getattr(self,'qt'+str(count))
			setattr(self,'tsink'+str(count),Gst.ElementFactory.make('rtmpsink', None))
			tsink = getattr(self,'tsink'+str(count))
			self.pipeline.add(q)
			self.pipeline.add(tsink)
			self.tee.link(q)
			q.link(tsink)
			tsink.set_property('location',value)

		comp_src_pad = self.mux.get_static_pad("src")
		self.pts_probe = comp_src_pad.add_probe(Gst.PadProbeType.BUFFER, self.pts_probe_cb, None)
		self.second_source = False
		self.forward_eos = False
		
	def run(self):
		self.file_to_stream = self.file_list.pop(0)
		if not len(self.file_list):
			self.forward_eos = True
		print ("Playing File from run: ", self.file_to_stream)		
		self.src.set_property('location', self.file_to_stream)
		self.pipeline.set_state(Gst.State.PLAYING)	
		self.mainloop.run()

	def pts_probe_cb(self, pad, info, data):
		buff = info.get_buffer()
		# print("Compositor pushed buffer.", buff.pts)
		self.last_pts = buff.pts
		return Gst.PadProbeReturn.PASS

	def demuxer_callback(self, demuxer, pad):
		#print (pad.get_property("template").name_template)
		if pad.get_property("template").name_template.startswith("video"):
			#print ("Got Video from Source")	
			qv_pad = self.vparse.get_static_pad("sink")
			qv_pad.set_active(True)
			self.vpad = pad
			self.vpad.link(qv_pad)
			self.vparse.link(self.q1)
			self.q1.link(self.mux)
			self.vparse.sync_state_with_parent()
			self.q1.sync_state_with_parent()
			self.mux.sync_state_with_parent()
			
			if self.second_source:
				self.vpad.set_offset(self.last_pts)
				print ("setting pts ", self.last_pts)

			if not self.forward_eos:
				self.eos_probe = self.vpad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, self.on_eos_event_cb, "audio")		
			self.mux.get_static_pad('src').send_event(Gst.Event.new_reconfigure())	
		elif pad.get_property("template").name_template.startswith("audio"):
			#print ("Got Audio from Source")	
			qa_pad = self.aparse.get_static_pad("sink")
			qa_pad.set_active(True)
			self.apad = pad
			self.apad.link(qa_pad)
			self.aparse.link(self.q2)
			self.q2.link(self.mux)
			self.aparse.sync_state_with_parent()
			self.q2.sync_state_with_parent()
			self.mux.sync_state_with_parent()
			if self.second_source:
				self.apad.set_offset(self.last_pts)
			self.mux.get_static_pad('src').send_event(Gst.Event.new_reconfigure())
	def get_running_time(self):
		ret, dur1 = self.pipeline.query_duration(Gst.Format.TIME)
		d1 = str(int(dur1 / Gst.SECOND))
		ret, dur = self.pipeline.query_position(Gst.Format.TIME)
		return dur1


	def srcpipe_disponse(self, src_error = False):
		print ("srcpipe_disponse %s" % (src_error))
		if not src_error:
			self.vpad.remove_probe(self.eos_probe)
			#self.vpad.unlink(self.vparse.get_static_pad('sink'))
			#self.apad.unlink(self.aparse.get_static_pad('sink'))
			#self.vparse.unlink(self.q1)
			#self.aparse.unlink(self.q2)
			#self.q1.unlink(self.mux)
			#self.q2.unlink(self.mux)


		self.src.set_state(Gst.State.NULL)	
		self.src.ref()
		del self.src
		self.demuxer.set_state(Gst.State.NULL)	
		self.demuxer.ref()
		del self.demuxer
		self.src = Gst.ElementFactory.make('souphttpsrc', None)
		self.file_to_stream = self.file_list.pop(0)
		if not len(self.file_list):
			self.forward_eos = True
		print ("Playing file", self.file_to_stream)
		self.src.set_property('location', self.file_to_stream)
		self.demuxer = Gst.ElementFactory.make('qtdemux', None)
		self.demuxer.connect("pad-added", self.demuxer_callback)

		self.pipeline.add(self.src)
		self.pipeline.add(self.demuxer)
		self.demuxer_sink_pad = self.demuxer.get_static_pad("sink")
		self.src.get_static_pad("src").link(self.demuxer_sink_pad)

		#self.demuxer_sink_pad.set_active(True)
		self.demuxer.sync_state_with_parent()

		self.src.sync_state_with_parent()
		self.second_source = True		
	def go_next_src_steps(self, src_error=False):
		print ("go_next_src_steps %s" % (src_error))
		#if not src_error:
		self.src.unlink(self.demuxer)
		#self.q3.unlink(self.tsink)
		if hasattr(self, 'apad'):
			self.apad.unlink(self.aparse.get_static_pad("sink"))
			self.vpad.unlink(self.vparse.get_static_pad("sink"))
		self.vparse.unlink(self.q1)
		self.aparse.unlink(self.q2)
		self.q1.unlink(self.mux)
		self.q2.unlink(self.mux)
		#self.mux.unlink(self.q3)
		#self.q3.unlink(self.tsink)
		if not src_error:
			self.pipeline.remove(self.src)
			self.pipeline.remove(self.demuxer)
		GLib.idle_add(self.srcpipe_disponse, src_error)

	def on_eos_event_cb(self, pad, info, data):
		event = info.get_event()
		#print("Receive event:", event.type)

		if event.type != Gst.EventType.EOS:
			return Gst.PadProbeReturn.PASS
		self.go_next_src_steps()
		
		return Gst.PadProbeReturn.DROP	
	def on_message(self, bus, message):
		if message.type == Gst.MessageType.STATE_CHANGED :
			if isinstance(message.src, Gst.Pipeline):
				old_state, new_state, pending_state = message.parse_state_changed()
				self.status = new_state.value_nick	
				print ("Pipeline state changed from %s to %s." % (old_state.value_nick, new_state.value_nick))
				#if new_state.value_nick == 'playing':
				#	print ("Setting Probe")
				#	print (self.pipeline.query_position(Gst.Format.TIME))

					#self.eos_probe = self.vpad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, self.on_eos_event_cb, "audio")  
			else:
				old_state, new_state, pending_state = message.parse_state_changed()
				self.status = new_state.value_nick	
				#print ("%s  state changed from %s to %s." % (message.src.get_name(), old_state.value_nick, new_state.value_nick))
		elif message.type == Gst.MessageType.STREAM_STATUS:
			status, owner = message.parse_stream_status()
			#print ("Stream  status %s: owner %s" % (status, owner.get_name()))
		elif message.type == Gst.MessageType.TAG:
			tags = message.parse_tag()
			#print ("Tag from %s: %s" % (message.src.get_name(), tags.to_string()))
		elif message.type == Gst.MessageType.ELEMENT:
			print ("Element type message")
		elif message.type == Gst.MessageType.WARNING:
			err, debug = message.parse_warning()
			print("GstWarning from %s: %s debug: %s" % (message.src.get_name(), err, debug))
			if  message.src.get_name().startswith("qtdemux") and "gst-stream-error-quark" in str(err):
				#print (err)
				self.go_next_src_steps(True)	
			if debug:
				debug = "\n".join(debug.splitlines()[1:])
			
				#details = debug.decode("utf-8", errors="replace")
				#print (debug)	
			
		#print("message: %s %s" % (message.type, message))

	def on_eos(self, bus, msg):
		print ("on EOS")		
		self.pipeline.set_state(Gst.State.NULL)
		#self.apad.unlink(self.aparse.get_static_pad("sink"))
		#self.vpad.unlink(self.vparse.get_static_pad("sink"))
		#time.sleep(5)

		#self.run()
		self.mainloop.quit()

	def on_error(self, bus, msg):
		gerror, debug_info = msg.parse_error()
		#print ("on_error %s : %s : %s" % (gerror, self.file_to_stream, msg.src.get_name()))
		#print ("on_error %s : %s : %s" % (debug_info, self.file_to_stream, msg.src.get_name()))
		if  msg.src.get_name().startswith("rtmpsink"):
			print (gerror)
			#self.pipeline.set_state(Gst.State.PAUSED)
			#self.pipeline.set_state(Gst.State.NULL)
			#print ("Trying to connect again after 5 second")
			#GLib.timeout_add_seconds(5, self.restart)
			self.pipeline.send_event(Gst.Event.new_eos())
			self.pipeline.set_state(Gst.State.NULL)
			self.mainloop.quit()
		elif  msg.src.get_name().startswith("qtdemux"):
			print (gerror)
		#	self.go_next_src_steps(True)
		else:
			self.pipeline.send_event(Gst.Event.new_eos())
			self.pipeline.set_state(Gst.State.NULL)
			self.mainloop.quit()


	def restart(self):
		self.pipeline.set_state(Gst.State.PLAYING)


			
#if __name__ == "__main__":
#	streamer=Streamer(['http://www.improsys.com/real.mp4','http://www.improsys.com/real.mp4','http://www.improsys.com/real.mp4'], ['rtmp://live-fra.twitch.tv/app/#live_406476462_iHwFE7IR8RnB6dhT5GJd52ET3dZ6Yj','rtmp://live-fra.twitch.tv/app/live_265843825_YDd60uC7RaDxYJEfJgmed6eqYg5Kve'])
#	streamer.run()	
#	print ("MainLoop done")




