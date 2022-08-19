# Gstreamer Gapless RTMP streamer without transcoding source

Combine multiple file without any gap and stream to multiple RTMP endpoints


media_info.py: used to get media information. It is necessary to have all source file same encoding profile, thats why media_info.py used.
streamer.py: Receives input files and output rtmp end points from the caller applictaion and then act accordingly.
