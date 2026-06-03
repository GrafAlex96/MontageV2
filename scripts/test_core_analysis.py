from app.services.analysis import VideoAnalyzer
import os

def test_analysis():
    video_path = "sample_video.mp4"
    if not os.path.exists(video_path):
        print("Sample video not found!")
        return

    analyzer = VideoAnalyzer(video_path)

    print("Detecting scenes...")
    scenes = analyzer.detect_scenes()
    print(f"Detected {len(scenes)} scenes.")

    print("Analyzing movement...")
    scenes = analyzer.analyze_movement(scenes)
    for i, scene in enumerate(scenes):
        print(f"Scene {i}: {scene.start_time:.2f}s - {scene.end_time:.2f}s, Movement: {scene.movement_score:.2f}")

    print("Detecting silence...")
    silences = analyzer.detect_silence()
    print(f"Detected {len(silences)} silent segments.")
    for silence in silences:
        print(f"Silence: {silence['start']:.2f}s - {silence.get('end', 'N/A')}s")

if __name__ == "__main__":
    test_analysis()
