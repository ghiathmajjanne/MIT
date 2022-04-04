const record = document.querySelector('.record');
const stop = document.querySelector('.stop');

// stop.disabled = true;

const context = new AudioContext();

const CHANNELS = 1;
const SAMPLE_RATE = context.sampleRate;
const CHUNK = 2048;

console.log(SAMPLE_RATE)
function getMic() {
	return navigator.mediaDevices.getUserMedia({
		audio: true
	})
}

const sio = io({
	cors: {
		origin: "http://127.0.0.1:5000",
		methods: ["GET", "POST"]
	}
});


sio.on("connect", () => {
	console.log("connected")
});

sio.on("disconnect", () => {
	console.log("disconnected")
});

sio.on("Detedted Note", (freq) => {
	console.log("Note detected; fundamental frequency:", freq)
});


// async because it has to wait for the promise of getMic() to be fulfilled,
// as getUserMedia retruns a promise of a media stream
async function setup() {
	const mic = await getMic();
	// to resume the context after loading the page because it gets suspended
	if (context.state === "suspended") {
		await context.resume();
	}
	const source = context.createMediaStreamSource(mic);

	context.audioWorklet.addModule("http://127.0.0.1:5000/static/AudioStreamProcessor.js").then(() => {
		let audioStream = new AudioWorkletNode(
			context,
			"AudioStream"
		)
		record.onclick = function () {
			source.connect(audioStream);
			console.log("recorder started");
			record.style.background = "red";
			record.style.color = "black";
		}

		stop.onclick = function () {
			source.disconnect();
			console.log("recorder stopped");
			record.style.background = "";
			record.style.color = "";
		}
		audioStream.port.onmessage = (event) => {
			// Handling data from the processor.
			sio.emit("data", event.data)
		};
	}).catch((e) => { console.log(e) });
}


setup()




