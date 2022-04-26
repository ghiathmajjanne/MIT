from collections import deque
import itertools
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, session
from flask_mysqldb import MySQL
import MySQLdb
from flask_socketio import SocketIO, emit
import numpy as np


CHUNK = 2048
THRESHOLD_WINDOW_SIZE = 11
THRESHOLD_MULTIPLIER = 10.8
RING_BUFFER_SIZE = 70
SAMPLE_RATE = 48000


class FrequencyDetector(object):

    FREQUENCY_RANGE = (70, 1200)

    def __init__(self, window_size, segments_buf=None):
        self._window_size = window_size
        if segments_buf is None:
            segments_buf = int(SAMPLE_RATE / window_size)
        self._segments_buf = segments_buf
        self._thresholding_window_size = THRESHOLD_WINDOW_SIZE

        self._last_spectrum = np.zeros(window_size, dtype=np.int16)
        self._last_flux = deque(
            np.zeros(segments_buf, dtype=np.int16), segments_buf)
        self._last_prunned_flux = 0

        self._hanning_window = np.hanning(window_size)
        # The zeros which will be used to double each segment size
        self._inner_pad = np.zeros(window_size)

        # To ignore the first peak just after starting the application
        self._first_peak = True

    def _get_flux_for_thresholding(self):
        """
        calculating a cap for thresholding from the last flux
        """
        return list(itertools.islice(
            self._last_flux,
            self._segments_buf - self._thresholding_window_size,
            self._segments_buf))

    def _find_onset(self, spectrum):
        """
        Calculates the difference between the current and last spectrum,
        then applies a thresholding function and checks if a peak occurred.

        Paremeters:
            spectrum

        Reruens:
            Boolean: True if an onset was detected
                     False if an onset was not detected
        """
        last_spectrum = self._last_spectrum
        flux = sum([max(spectrum[n] - last_spectrum[n], 0)
                    for n in range(self._window_size)])
        self._last_flux.append(flux)
        fluxing = self._get_flux_for_thresholding()
        thresholded = np.mean(fluxing) * THRESHOLD_MULTIPLIER
        prunned = flux - thresholded if thresholded <= flux else 0
        peak = True if prunned > self._last_prunned_flux else False
        self._last_prunned_flux = prunned
        return peak

    def _find_fundamental_freq(self, samples):
        """
        search for maximum between 1200Hz and 70Hz

        Retruns:
            Double: the fundemantal frequency fetected 
            None:   if the frequency is out of range
        """
        cepstrum = self._cepstrum(samples)

        min_freq, max_freq = self.FREQUENCY_RANGE
        start = int(SAMPLE_RATE / max_freq)
        end = int(SAMPLE_RATE / min_freq)
        narrowed_cepstrum = cepstrum[start:end]

        peak_ix = narrowed_cepstrum.argmax()
        freq = SAMPLE_RATE / (start + peak_ix)

        if freq < min_freq or freq > max_freq:
            # Ignore the note out of the desired frequency range
            return

        return freq

    def _autopower_spectrum(self, samples):
        """
        Calculates a power spectrum of the given data using the Hanning window.

        Parameters:
            samples (float[2048]): an array of size 2048

        Retruns:
            autopower spectrum
        """
        windowed = samples * self._hanning_window
        # Add 0s to double the length of the data
        padded = np.append(windowed, self._inner_pad)
        # Take the Fourier Transform and scale by the number of samples
        spectrum = np.fft.fft(padded) / self._window_size
        autopower = np.abs(spectrum * np.conj(spectrum))
        return autopower[:self._window_size]

    def _cepstrum(self, samples):
        """
        Calculates the complex cepstrum of a real sequence.
        A Cepstrum is the inverse fft of the log of the fft the signal.
        We use the cepsrtrum instead of a spectrum because it deals with the harmonic
        frequencies better than the normal spectrum, and musical instruments has a lot of
        harmonic frequencies in their signals.

        Retruns:
            cepstrum
        """
        abs_spectrum = np.abs(np.fft.fft(samples))
        log_spectrum = np.log(abs_spectrum)
        cepstrum = np.fft.ifft(log_spectrum).real
        return cepstrum

    def process_data(self, data):
        """
        Processes the frame and returns the fundematal frequency detected.

        Parameters:
        data (bytes[2048]): a buffer of data of size 2048

        Retruns:
        int: the fundemental frequency detected
        None: if no fundemental frequency detected
        """

        data = np.frombuffer(data, dtype=np.float32)

        spectrum = self._autopower_spectrum(data)

        onset = self._find_onset(spectrum)
        self._last_spectrum = spectrum

        if self._first_peak:
            self._first_peak = False
            return

        if onset:
            freq = self._find_fundamental_freq(data)
            return freq

# end of the FrequencyDetector Class


# intialize the frequancy detector
freq_Detector = FrequencyDetector(window_size=CHUNK,
                                  segments_buf=RING_BUFFER_SIZE)

app = Flask(__name__)
socket = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

app.secret_key = "1234567890"

app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "root"
app.config["MYSQL_DB"] = "users"

db = MySQL(app)


# request routing methods

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if "username" in request.form and "password" in request.form:
            username = request.form["username"]
            password = request.form["password"]
            cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(
                "SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            info = cursor.fetchone()
            if info is not None:
                if info["username"] == username and info["password"] == password:
                    session["loginSuccessful"] = True
                    return redirect(url_for("index"))
            else:
                return "Incorrect username or password"

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def create_new_user():
    if request.method == "POST":
        if "username" in request.form and "password" in request.form and "re_password" in request.form:
            username = request.form["username"]
            password = request.form["password"]
            re_password = request.form["re_password"]
            if (password != re_password):
                return "Passwords Don't match"
            check_username = db.connection.cursor(MySQLdb.cursors.DictCursor)

            check_username.execute(
                "SELECT * FROM users WHERE username=%s", [username])
            info = check_username.fetchone()
            if info is not None:
                if info["username"] == username:
                    return "Username already exists"

            cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(
                "INSERT INTO users.users(username, password)VALUES(%s, %s)", (username, password))

            db.connection.commit()
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/index")
def index():
    if session["loginSuccessful"] == True:
        print("sending index.html")
        return render_template("index.html")
    return render_template("index.html")


@app.route("/static/AudioStreamProcessor.js", methods=["GET"])
def static_dir():
    response = send_from_directory("static", "AudioStreamProcessor.js")
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@socket.on('connect')
def connect():
    print("[CLIENT CONNECTED]:", request.sid)


@socket.on('disconnect')
def disconn():
    print("[CLIENT DISCONNECTED]:", request.sid)


@socket.on('data')
def recieveData(data):
    data = data["audioBuffer"]
    data = np.frombuffer(data, dtype=np.float32)
    freq = freq_Detector.process_data(data)
    if freq:
        emit("Detedted Note", freq)


# main method
if __name__ == "__main__":
    socket.run(app=app, port=5000, debug=True)
