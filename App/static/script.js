document.addEventListener('DOMContentLoaded', () => {
    const jarvisOrb = document.getElementById('jarvis-orb');
    const jarvisWaveform = document.getElementById('jarvis-waveform');
    const textOutputElement = document.getElementById('jarvis-text-output').querySelector('p');
    const statusIndicator = document.getElementById('status-indicator');
    const MAX_WAVEFORM_BARS = 25;

    function createWaveformBars() {
        jarvisWaveform.innerHTML = '';
        for (let i = 0; i < MAX_WAVEFORM_BARS; i++) {
            const bar = document.createElement('div');
            bar.classList.add('waveform-bar');
            const delay = Math.random() * 0.6; 
            const duration = 0.4 + Math.random() * 0.6; 
            bar.style.animation = `wave ${duration}s ${delay}s infinite ease-in-out`;
            bar.style.transform = `scaleY(${0.1 + Math.random() * 0.2})`; 
            jarvisWaveform.appendChild(bar);
        }
    }

    function updateTextOutput(text, isError = false) {
        textOutputElement.textContent = text;
        textOutputElement.style.color = isError ? 'var(--status-color-error)' : 'var(--text-color)';
    }

    function setOrbState(state) {
        jarvisOrb.classList.remove('speaking', 'active', 'deactivated', 'offline', 'idle');
        if (state === 'speaking') {
            jarvisOrb.classList.add('active'); 
            jarvisOrb.classList.add('speaking');
        } else if (state === 'active') {
            jarvisOrb.classList.add('active');
        } else if (state === 'deactivated') {
            jarvisOrb.classList.add('deactivated');
        } else if (state === 'offline') {
            jarvisOrb.classList.add('offline');
        } else {
            jarvisOrb.classList.add('idle');
        }
    }
    
    updateTextOutput("Initializing Interface...");
    setOrbState('idle');

    if (!!window.EventSource) {
        const source = new EventSource("/listen_events");

        source.onopen = function() {
            console.log("SSE Connection opened.");
            statusIndicator.textContent = "Online";
            statusIndicator.style.color = "var(--status-color-online)";
            updateTextOutput("Jarvis Online. Awaiting wake word...");
            setOrbState('deactivated');
        };

        source.onmessage = function(event) {
            try {
                const eventData = JSON.parse(event.data);

                if (eventData.text !== undefined) {
                    updateTextOutput(String(eventData.text));
                }

                let nextOrbState = null;

                switch (eventData.event) {
                    case "speaking_start":
                        nextOrbState = 'speaking';
                        jarvisWaveform.classList.add("speaking");
                        if (jarvisWaveform.children.length === 0 || Math.random() < 0.1) {
                            createWaveformBars();
                        }
                        statusIndicator.textContent = "Jarvis Speaking";
                        statusIndicator.style.color = "var(--status-color-speaking)";
                        break;
                    case "speaking_end":
                        jarvisWaveform.classList.remove("speaking");
                        const currentStatus = statusIndicator.textContent.toLowerCase();
                        if (currentStatus.includes("listening (wake word)") || currentStatus === "idle" || currentStatus === "online") {
                            nextOrbState = 'deactivated';
                        } else if (currentStatus.includes("activated") || currentStatus.includes("awaiting command") || currentStatus.includes("command heard") || currentStatus.includes("processing") || currentStatus.includes("task complete")) {
                            nextOrbState = 'active';
                        } else {
                             nextOrbState = 'idle'; 
                        }
                        break;
                    case "listening_wake_word":
                        nextOrbState = 'deactivated';
                        statusIndicator.textContent = "Listening (Wake Word)";
                        statusIndicator.style.color = "var(--status-color-default)";
                        updateTextOutput(eventData.text || "Say 'Hey Jarvis'...");
                        break;
                    case "wake_word_detected":
                        nextOrbState = 'active';
                        statusIndicator.textContent = "Activated";
                        statusIndicator.style.color = "var(--status-color-active)";
                        break;
                    case "listening_command":
                        nextOrbState = 'active';
                        statusIndicator.textContent = "Awaiting Command";
                        statusIndicator.style.color = "var(--status-color-active)";
                        updateTextOutput(eventData.text || "Listening for your command...");
                        break;
                    case "command_recognised":
                        nextOrbState = 'active';
                        statusIndicator.textContent = "Command Heard";
                        statusIndicator.style.color = "var(--status-color-processing)";
                        break;
                    case "processing_command":
                        nextOrbState = 'active';
                        statusIndicator.textContent = "Processing...";
                        statusIndicator.style.color = "var(--status-color-processing)";
                        break;
                    case "command_processed":
                        nextOrbState = 'active';
                        statusIndicator.textContent = "Task Complete";
                        statusIndicator.style.color = "#2ecc71";
                        break;
                    case "idle":
                        nextOrbState = 'deactivated';
                        statusIndicator.textContent = "Idle";
                        statusIndicator.style.color = "var(--status-color-default)";
                        updateTextOutput("Jarvis is deactivated. Say the wake word...");
                        break;
                    case "jarvis_status":
                        statusIndicator.textContent = eventData.text || "Status Update";
                        if (eventData.text) {
                            const textLower = eventData.text.toLowerCase();
                            if (textLower.includes("offline")) {
                                statusIndicator.style.color = "var(--status-color-error)";
                                nextOrbState = 'offline';
                            } else if (textLower.includes("online") || textLower.includes("starting up")){
                                statusIndicator.style.color = "var(--status-color-online)";
                                nextOrbState = 'deactivated';
                            }
                        }
                        break;
                    default:
                        if (eventData.event === "display_text" && !jarvisOrb.classList.contains('speaking')){
                            const fallbackStatus = statusIndicator.textContent.toLowerCase();
                             if (fallbackStatus.includes("listening (wake word)") || fallbackStatus === "idle" || fallbackStatus === "online") {
                                nextOrbState = 'deactivated';
                            } else if (jarvisOrb.classList.contains('active')) {
                                nextOrbState = 'active';
                            } else {
                                nextOrbState = 'idle';
                            }
                        }
                }
                if (nextOrbState) {
                    setOrbState(nextOrbState);
                }

            } catch (e) {
                console.error("Error parsing SSE data or handling event:", e, "Raw data:", event.data);
                updateTextOutput("Received malformed data from server.", true);
            }
        };

        source.onerror = function(err) {
            console.error("EventSource failed:", err);
            setOrbState('offline');
            jarvisWaveform.classList.remove("speaking");
            statusIndicator.textContent = "Disconnected";
            statusIndicator.style.color = "var(--status-color-error)";
            updateTextOutput("Connection to Jarvis lost. Please check server and refresh.", true);
        };

    } else {
        updateTextOutput("Browser not supported for live updates.", true);
        statusIndicator.textContent = "SSE Not Supported";
        setOrbState('offline');
    }
});