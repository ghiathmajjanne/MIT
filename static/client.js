const start_button = document.querySelector('.start');
const stop_button = document.querySelector('.stop');
stop_button.disabled = true;

const context = new AudioContext();

const CHANNELS = 1;
const SAMPLE_RATE = context.sampleRate;
const CHUNK = 2048;

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
	console.log("connected to the server")
});

sio.on("disconnect", () => {
	console.log("disconnected from the server")
});

sio.on("Detedted Note", (freq) => {
	console.log("Note detected; fundamental frequency:", freq)
	//TODO: Added the functionality of the game
});


// covers all strings of the guitar with 11 frets each
const frequencies = [
	[329, 349, 370, 392, 415, 440, 466, 494, 523, 554, 587, 622],
	[247, 262, 277, 294, 311, 329, 349, 370, 392, 415, 440, 466],
	[196, 208, 220, 233, 247, 262, 277, 294, 311, 329, 349, 370],
	[147, 156, 165, 175, 185, 196, 208, 220, 233, 247, 262, 277],
	[110, 117, 123, 131, 139, 147, 156, 165, 175, 185, 196, 208],
	[82, 87, 92, 98, 104, 110, 117, 123, 131, 139, 147, 156]
];

const guitarStrings = ["e", "B", "G", "D", "A", "E"];

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
		start_button.onclick = function () {
			source.connect(audioStream);
			console.log("Stream started");
			stop_button.disabled = false;
			start_button.disabled = true;
			let randString = Math.floor(Math.random() * 6);
			console.log(randString);
			let randFret = Math.floor(Math.random() * 12);
			console.log(randFret);
			console.log("Play " + guitarStrings[randString] + randFret);

		}

		stop_button.onclick = function () {
			source.disconnect();
			stop_button.disabled = true;
			start_button.disabled = false;
			console.log("Stream stopped");
			start_button.style.background = "";
			start_button.style.color = "";
		}
		audioStream.port.onmessage = (event) => {
			// Handling data from the processor.
			sio.emit("data", event.data)
		};
	}).catch((e) => { console.log(e) });


}


setup()







