const start_button = document.getElementById("start_btn");
const stop_button = document.getElementById("stop_btn");
const note_txtbox = document.getElementById("note_to_play");
const note_card = document.getElementById("note_card");
const score_modal = document.getElementById("score_text");

const context = new AudioContext();

let randString = -1;
let randFret = -1;
let score = 0;
let numNotes = 0;


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


// generates a randome note and displayes it to the screen
function startGame() {
	randString = Math.floor(Math.random() * 6);
	randFret = Math.floor(Math.random() * 12);
	console.log("Play " + guitarStrings[randString] + randFret);
	note_txtbox.innerHTML = guitarStrings[randString] + randFret.toString()
}

sio.on("Detedted Note", (freq) => {
	console.log("Note detected; fundamental frequency:", freq)
	if (freq < frequencies[randString][randFret] * 1.03 && freq > frequencies[randString][randFret] * 0.97) {
		score++;
		console.log("Correct");
		note_card.style.background = "rgb(110, 220, 20)";
		window.setTimeout(reset_note_card, 300);
	} else {
		console.log("Wrong");
		note_card.style.background = "rgb(216, 70, 40)";
		window.setTimeout(reset_note_card, 300);
	}
	numNotes++;
	startGame();
});


// resets the background color of the note card to white
function reset_note_card() {
	note_card.style.background = "white";
}


// covers all strings of the guitar with 11 frets each
const frequencies = [
	[329, 349, 370, 392, 415, 440, 466, 494, 523, 554, 587, 622],
	[247, 262, 277, 294, 311, 329, 349, 370, 392, 415, 440, 466],
	[196, 208, 220, 233, 247, 262, 277, 294, 311, 329, 349, 370],
	[147, 156, 165, 175, 185, 196, 208, 220, 233, 247, 262, 277],
	[110, 117, 123, 131, 139, 147, 156, 165, 175, 185, 196, 208],
	[82, 87, 92, 98, 104, 110, 117, 123, 131, 139, 147, 156]
];

// names of the 6 guitar strings
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
			startGame();
			source.connect(audioStream);
			console.log("Stream started");
			stop_button.disabled = false;
			start_button.disabled = true;
		}

		stop_button.onclick = function () {
			source.disconnect();
			stop_button.disabled = true;
			start_button.disabled = false;
			console.log("Stream stopped");
			randString = -1;
			randFret = -1;
			note_txtbox.innerHTML = "";
			console.log("***** the Game Ended *****");
			console.log("Score: " + score + "/" + numNotes);
			score_modal.innerHTML = "Score: " + score + "/" + numNotes;
			score = 0;
			numNotes = 0;
		}

		audioStream.port.onmessage = (event) => {
			// Handling data from the processor.
			sio.emit("data", event.data)
		};
	}).catch((e) => { console.log(e) });
}

setup()
