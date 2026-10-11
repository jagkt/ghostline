from faster_whisper import WhisperModel
import time


MODEL_SIZE = "small" # good accuracy/speed balance for CPU

print("Loading Model ....")
t0 = time.time()
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
print(f"Model loaded in {time.time() - t0:.1f}s")

t0 = time.time()
segments, info = model.transcribe("/tmp/test.wav", beam_size=5)
segments = list(segments) # generator, force evaluation to include it in timing
elapsed = time.time() -  t0


print(f"Detected Language: {info.language} (probability {info.language_probability:.2f})")
print(f"Transcription took {elapsed:.2f}s")

for segment in segments:
	print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
