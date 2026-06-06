import scripts.render_live_demo_video as demo


def test_live_demo_video_exports_60fps_at_2_5x_speed():
    assert demo.ENCODE_FPS == 60
    assert demo.PLAYBACK_SPEED == 2.5
    assert demo.FPS * demo.PLAYBACK_SPEED == demo.ENCODE_FPS
    assert demo.TOTAL_FRAMES / demo.ENCODE_FPS == demo.DURATION / demo.PLAYBACK_SPEED
