// State
let callSocket = null;
let eventSocket = null;
let audioInputContext = null;
let audioOutputContext = null;
let audioInputSource = null;
let audioProcessor = null;
let micStream = null;
let isMuted = false;
let callDuration = 0;
let callTimer = null;
let nextPlayTime = 0;
let allAppointments = [];
let currentFilter = 'ALL';

// DOM Elements
const startCallBtn = document.getElementById('startCallBtn');
const phoneModal = document.getElementById('phoneModal');
const muteBtn = document.getElementById('muteBtn');
const endCallBtn = document.getElementById('endCallBtn');
const callStatusText = document.getElementById('callStatusText');
const transcriptBox = document.getElementById('transcriptBox');
const actionToast = document.getElementById('actionToast');
const actionToastText = document.getElementById('actionToastText');
const doctorsGrid = document.getElementById('doctorsGrid');
const appointmentsTableBody = document.getElementById('appointmentsTableBody');
const appointmentsCountBadge = document.getElementById('appointmentsCountBadge');

// Fetch Doctors and Appointments
async function fetchDoctors() {
  try {
    const res = await fetch('/api/doctors');
    if (!res.ok) return;
    const doctors = await res.json();
    renderDoctors(doctors);
  } catch (err) {
    console.error('Failed to load doctors:', err);
  }
}

async function fetchAppointments() {
  try {
    const res = await fetch('/api/appointments');
    if (!res.ok) return;
    allAppointments = await res.json();
    renderAppointments();
  } catch (err) {
    console.error('Failed to load appointments:', err);
  }
}

function isSlotPast(dateStr, timeStr) {
  try {
    const slotDate = new Date(`${dateStr} ${timeStr}`);
    return slotDate <= new Date();
  } catch (e) {
    return false;
  }
}

function renderDoctors(doctors) {
  if (!doctorsGrid) return;
  doctorsGrid.innerHTML = '';

  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

  const tmrw = new Date(now);
  tmrw.setDate(tmrw.getDate() + 1);
  const tomorrowStr = `${tmrw.getFullYear()}-${pad(tmrw.getMonth() + 1)}-${pad(tmrw.getDate())}`;

  doctors.forEach((doc) => {
    // Only display active slots for today and tomorrow
    const activeDocSlots = (doc.slots || []).filter(
      (s) => s.date === todayStr || s.date === tomorrowStr
    );
    const availableUpcomingSlots = activeDocSlots.filter(
      (s) => !s.is_booked && !isSlotPast(s.date, s.time)
    );
    const card = document.createElement('div');
    card.className = 'doctor-card';

    const slotPills = activeDocSlots
      .map((s) => {
        const isPast = isSlotPast(s.date, s.time);
        let statusClass = 'available';
        let titleExtra = '';
        if (s.is_booked) {
          statusClass = 'booked';
          titleExtra = ' (Booked)';
        } else if (isPast) {
          statusClass = 'past';
          titleExtra = ' (Passed)';
        }
        const dayLabel = s.date === tomorrowStr ? 'Tomorrow' : 'Today';
        return `<span class="slot-pill ${statusClass}" title="${s.date} ${s.time}${titleExtra}">${dayLabel} ${s.time}</span>`;
      })
      .join('');

    card.innerHTML = `
      <div>
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <div class="doc-name">${doc.name}</div>
            <div class="doc-spec">${doc.specialty}</div>
          </div>
          <span class="badge">${availableUpcomingSlots.length} open</span>
        </div>
        <div class="slots-container">
          <div class="slots-label">Doctor Schedule (Today & Tomorrow)</div>
          <div class="slot-pills">${slotPills}</div>
        </div>
      </div>
    `;
    doctorsGrid.appendChild(card);
  });
}

function renderAppointments() {
  if (!appointmentsTableBody) return;

  const totalCount = allAppointments.length;
  const confirmedCount = allAppointments.filter((a) => a.status === 'CONFIRMED').length;
  const cancelledCount = allAppointments.filter((a) => a.status === 'CANCELLED').length;

  const countAll = document.getElementById('countAll');
  const countConfirmed = document.getElementById('countConfirmed');
  const countCancelled = document.getElementById('countCancelled');
  if (countAll) countAll.textContent = totalCount;
  if (countConfirmed) countConfirmed.textContent = confirmedCount;
  if (countCancelled) countCancelled.textContent = cancelledCount;

  // Filter list
  const filtered = allAppointments.filter((apt) => {
    if (currentFilter === 'CONFIRMED') return apt.status === 'CONFIRMED';
    if (currentFilter === 'CANCELLED') return apt.status === 'CANCELLED';
    return true;
  });

  if (appointmentsCountBadge) {
    if (currentFilter === 'ALL') {
      appointmentsCountBadge.textContent = `${totalCount} Total`;
    } else if (currentFilter === 'CONFIRMED') {
      appointmentsCountBadge.textContent = `${confirmedCount} Confirmed`;
    } else {
      appointmentsCountBadge.textContent = `${cancelledCount} Cancelled`;
    }
  }

  if (filtered.length === 0) {
    const label = currentFilter === 'ALL' ? 'recorded' : currentFilter.toLowerCase();
    appointmentsTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#94a3b8; padding:28px;">No ${label} appointments found.</td></tr>`;
    return;
  }

  appointmentsTableBody.innerHTML = filtered
    .map(
      (apt) => `
      <tr>
        <td class="phone-badge">📞 ${apt.patient_phone}</td>
        <td style="font-weight:600;">${apt.doctor_name}</td>
        <td style="color:#64748b;">${apt.specialty}</td>
        <td>${apt.date} • ${apt.time}</td>
        <td>
          <span class="status-tag ${apt.status === 'CONFIRMED' ? 'confirmed' : 'cancelled'}">
            ${apt.status === 'CONFIRMED' ? '✓ Confirmed' : '✕ Cancelled'}
          </span>
        </td>
      </tr>
    `
    )
    .join('');
}

// Dashboard Events WebSocket (Transcripts & Auto-update)
function initDashboardWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  eventSocket = new WebSocket(`${protocol}//${window.location.host}/ws`);

  eventSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'transcript') {
        appendTranscript(data.speaker, data.text);
      } else if (data.type === 'database_update') {
        showToast(data.data?.message || `Appointment ${data.action}`);
        fetchDoctors();
        fetchAppointments();
      }
    } catch (e) {
      console.error(e);
    }
  };

  eventSocket.onclose = () => {
    setTimeout(initDashboardWebSocket, 2000);
  };
}

function appendTranscript(speaker, text) {
  const placeholder = transcriptBox.querySelector('.transcript-placeholder');
  if (placeholder) placeholder.remove();

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${speaker}`;
  bubble.textContent = text;

  const meta = document.createElement('div');
  meta.className = `bubble-meta ${speaker === 'user' ? 'user-meta' : ''}`;
  meta.textContent = speaker === 'user' ? 'You' : 'Cura Receptionist';

  const container = document.createElement('div');
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.appendChild(bubble);
  container.appendChild(meta);

  transcriptBox.appendChild(container);
  transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

function showToast(message) {
  actionToastText.textContent = message;
  actionToast.classList.remove('hidden');
  setTimeout(() => {
    actionToast.classList.add('hidden');
  }, 4500);
}

// Downsample float32 buffer to target 16kHz
function downsampleBuffer(buffer, inSampleRate, outSampleRate) {
  if (outSampleRate === inSampleRate) return buffer;
  const ratio = inSampleRate / outSampleRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0, count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

// Audio Playback Function (Streams 24kHz raw PCM from Assistant)
function playPCMChunk(arrayBuffer) {
  if (!audioOutputContext) {
    audioOutputContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
  }

  if (audioOutputContext.state === 'suspended') {
    audioOutputContext.resume();
  }

  const int16 = new Int16Array(arrayBuffer);
  if (int16.length === 0) return;

  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768.0;
  }

  const buffer = audioOutputContext.createBuffer(1, float32.length, 24000);
  buffer.copyToChannel(float32, 0);

  const source = audioOutputContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioOutputContext.destination);

  const now = audioOutputContext.currentTime;
    if (nextPlayTime < now || nextPlayTime > now + 1.0) {
      nextPlayTime = now;
    }
    source.start(nextPlayTime);
    nextPlayTime += buffer.duration;
  }

  // Voice Call WebSocket Connection (Mic Input & Speaker Output)
  async function startCall() {
    try {
      startCallBtn.disabled = true;
      startCallBtn.innerHTML = `<span class="call-icon">📞</span><span>Connecting...</span>`;
      transcriptBox.innerHTML = `<div class="transcript-placeholder">Connecting audio directly over WebSocket...</div>`;
      phoneModal.classList.remove('hidden');
      callStatusText.textContent = 'Connecting audio...';
      callStatusText.className = 'call-status';

      // 1. Initialize & resume audio output context
      if (!audioOutputContext) {
        audioOutputContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
      }
      await audioOutputContext.resume();

      // 2. Request Microphone Access
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      // 3. Open Call WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      callSocket = new WebSocket(`${protocol}//${window.location.host}/ws/call`);
      callSocket.binaryType = 'arraybuffer';

      callSocket.onopen = async () => {
        callStatusText.textContent = 'Connected (00:00)';
        callStatusText.className = 'call-status connected';

        callDuration = 0;
        nextPlayTime = 0;
        callTimer = setInterval(() => {
          callDuration++;
          const mins = String(Math.floor(callDuration / 60)).padStart(2, '0');
          const secs = String(callDuration % 60).padStart(2, '0');
          callStatusText.textContent = `Connected (${mins}:${secs})`;
        }, 1000);

        // 4. Setup Input AudioContext & Processing
        audioInputContext = new (window.AudioContext || window.webkitAudioContext)();
        await audioInputContext.resume();

        audioInputSource = audioInputContext.createMediaStreamSource(micStream);
        // Buffer size 4096 gives ~85ms at 48kHz
        audioProcessor = audioInputContext.createScriptProcessor(4096, 1, 1);

        const actualSampleRate = audioInputContext.sampleRate;
        console.log(`Mic initialized at hardware rate: ${actualSampleRate}Hz. Downsampling to 16000Hz.`);

        audioProcessor.onaudioprocess = (e) => {
          if (isMuted || !callSocket || callSocket.readyState !== WebSocket.OPEN) return;
          const inputData = e.inputBuffer.getChannelData(0);

          // Downsample to standard 16kHz
          const downsampled = downsampleBuffer(inputData, actualSampleRate, 16000);

          // Convert Float32 to 16-bit PCM Int16
          const pcm16 = new Int16Array(downsampled.length);
          for (let i = 0; i < downsampled.length; i++) {
            const s = Math.max(-1, Math.min(1, downsampled[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }

          callSocket.send(pcm16.buffer);
        };

        audioInputSource.connect(audioProcessor);
        audioProcessor.connect(audioInputContext.destination);
      };

          callSocket.onmessage = async (event) => {
            let data = event.data;
            if (data instanceof Blob) {
              data = await data.arrayBuffer();
            }
            if (data instanceof ArrayBuffer && data.byteLength > 0) {
              playPCMChunk(data);
            }
          };

          callSocket.onerror = (e) => {
            console.error('WebSocket call error:', e);
          };

          callSocket.onclose = () => {
            endCall();
          };

        } catch (err) {
          console.error('Start call error:', err);
          alert('Microphone access denied or error starting call.');
          endCall();
        } finally {
          startCallBtn.disabled = false;
          startCallBtn.innerHTML = `
            <span class="call-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 0 0-1.01.24l-2.2 2.2a15.053 15.053 0 0 1-6.59-6.59l2.2-2.21a.96.96 0 0 0 .25-1.01A11.36 11.36 0 0 1 8.5 3.99c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1 0 9.39 7.61 17 17 17 .55 0 1-.45 1-1v-3.61c0-.55-.45-1-1-1z"/>
              </svg>
            </span>
            <span>Start Voice Agent</span>`;
        }
      }

      function endCall() {
        clearInterval(callTimer);
        callStatusText.textContent = 'Call Ended';
        callStatusText.className = 'call-status';

        // Stop Audio Nodes
        if (audioProcessor) {
          try { audioProcessor.disconnect(); } catch (e) { }
          audioProcessor = null;
        }
        if (audioInputSource) {
          try { audioInputSource.disconnect(); } catch (e) { }
          audioInputSource = null;
        }
        if (audioInputContext) {
          try { audioInputContext.close(); } catch (e) { }
          audioInputContext = null;
        }
        if (micStream) {
          micStream.getTracks().forEach((track) => track.stop());
          micStream = null;
        }

        // Close Call Socket
        if (callSocket) {
          if (callSocket.readyState === WebSocket.OPEN) {
            callSocket.close();
          }
          callSocket = null;
        }

        setTimeout(() => {
          phoneModal.classList.add('hidden');
        }, 1000);
      }

      function toggleMute() {
        isMuted = !isMuted;
        if (isMuted) {
          muteBtn.classList.add('active');
          muteBtn.textContent = '🔇';
        } else {
          muteBtn.classList.remove('active');
          muteBtn.textContent = '🎤';
        }
      }

      // Event Listeners
      startCallBtn.addEventListener('click', startCall);
      endCallBtn.addEventListener('click', endCall);
      muteBtn.addEventListener('click', toggleMute);

      // Filter Tabs for Appointments
      const filterTabs = document.querySelectorAll('.filter-tab');
      filterTabs.forEach((tab) => {
        tab.addEventListener('click', () => {
          filterTabs.forEach((t) => t.classList.remove('active'));
          tab.classList.add('active');
          currentFilter = tab.getAttribute('data-filter') || 'ALL';
          renderAppointments();
        });
      });

      // Initialize Dashboard
      fetchDoctors();
      fetchAppointments();
      initDashboardWebSocket();
