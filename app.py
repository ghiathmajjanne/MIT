from collections import deque
import itertools
from flask import Flask, request, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import numpy as np


CHUNK = 2048
THRESHOLD_WINDOW_SIZE = 11
THRESHOLD_MULTIPLIER = 10.65

DEFAULT_BPM = 120
DEFAULT_PITCH = 64
DEFAULT_VELOCITY = 64

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
        Calculates a power spectrum of the given data using the Hamming window.
        why we use autopower spectrum and not a normal spectum:
        https://community.sw.siemens.com/s/article/spectrum-versus-autopower
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
            print("Note detected; fundamental frequency: ", freq)
            return freq

# end of the FrequencyDetector Class


# intialize the frequancy detector
freq_Detector = FrequencyDetector(window_size=CHUNK,
                                  segments_buf=RING_BUFFER_SIZE)

app = Flask(__name__)
socket = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")


@app.route('/')
def index():
    print("sending index.html")
    return render_template('index.html')


@app.route("/static/AudioStreamProcessor.js", methods=['GET'])
def static_dir():
    response = send_from_directory("static", "AudioStreamProcessor.js")
    response.headers.add('Access-Control-Allow-Origin', '*')
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
