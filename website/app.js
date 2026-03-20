const filterButtons = document.querySelectorAll(".filter-button");
const sessionGrid = document.querySelector("#session-grid");
const libraryStatus = document.querySelector("#library-status");
const AUDIO_LOOP_WINDOW_SECONDS = 2 * 60 * 60;

let activeFilter = "all";

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char];
  });
}

function renderMedia(session) {
  if (session.kind === "video" && session.mediaPath) {
    return `
      <video controls preload="metadata" ${session.posterPath ? `poster="${escapeHtml(session.posterPath)}"` : ""}>
        <source src="${escapeHtml(session.mediaPath)}" type="video/mp4" />
      </video>
    `;
  }

  if (session.kind === "audio" && session.mediaPath) {
    return `
      <audio controls preload="metadata" data-loop-window-seconds="${AUDIO_LOOP_WINDOW_SECONDS}">
        <source src="${escapeHtml(session.mediaPath)}" type="audio/mpeg" />
      </audio>
    `;
  }

  return `<div class="session-unavailable">This session is not ready to play yet.</div>`;
}

function setupTimedAudioLoop(audio) {
  if (audio.dataset.loopBound === "true") {
    return;
  }

  audio.dataset.loopBound = "true";

  const loopWindowSeconds = Number(audio.dataset.loopWindowSeconds || AUDIO_LOOP_WINDOW_SECONDS);

  const resetLoopSession = () => {
    audio.dataset.loopStartedAt = "";
  };

  const markLoopSessionStarted = () => {
    if (!audio.dataset.loopStartedAt) {
      audio.dataset.loopStartedAt = String(Date.now());
    }
  };

  audio.addEventListener("play", () => {
    markLoopSessionStarted();
  });

  audio.addEventListener("ended", () => {
    const startedAt = Number(audio.dataset.loopStartedAt || 0);
    if (!startedAt) {
      return;
    }

    const elapsedSeconds = (Date.now() - startedAt) / 1000;
    if (elapsedSeconds < loopWindowSeconds) {
      audio.currentTime = 0;
      void audio.play().catch(() => {});
      return;
    }

    resetLoopSession();
  });
}

function bindAudioLoops() {
  const audioPlayers = sessionGrid.querySelectorAll("audio[data-loop-window-seconds]");
  audioPlayers.forEach(setupTimedAudioLoop);
}

function renderSessions(sessions) {
const normalizedSessions = sessions.filter((session) => {
  const mediaPath = String(session.mediaPath || "").toLowerCase();
  return session.kind === "audio" && mediaPath.endsWith(".mp3");
});

  const filteredSessions = normalizedSessions.filter((session) => {
    return activeFilter === "all" || session.kind === activeFilter;
  });

  if (!filteredSessions.length) {
    sessionGrid.innerHTML = "";
    libraryStatus.textContent = "There are no sessions in this category yet.";
    return;
  }

  sessionGrid.innerHTML = filteredSessions
    .map((session) => {
      return `
        <article class="session-card" data-kind="${escapeHtml(session.kind)}">
          <div class="session-cover ${escapeHtml(session.coverTheme || "warm-cover")}">
            <span class="session-tag">${escapeHtml(session.kindLabel)}</span>
            <h3>${escapeHtml(session.title)}</h3>
            <p>${escapeHtml(session.subtitle)}</p>
          </div>
          <div class="session-body">
            <p class="session-meta">${escapeHtml(session.meta)}</p>
            ${renderMedia(session)}
            <p class="session-description">${escapeHtml(session.description)}</p>
          </div>
        </article>
      `;
    })
    .join("");

  bindAudioLoops();
  libraryStatus.textContent = `${filteredSessions.length} gentle session${filteredSessions.length === 1 ? "" : "s"} available.`;
}

async function loadSessions() {
  try {
    const payload = window.SESSION_LIBRARY || { sessions: [] };
    renderSessions(Array.isArray(payload.sessions) ? payload.sessions : []);
  } catch (error) {
    sessionGrid.innerHTML = "";
    libraryStatus.textContent = "The session library is unavailable right now. Run the sync again to refresh this space.";
  }
}

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activeFilter = button.dataset.filter || "all";
    filterButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    loadSessions();
  });
});

loadSessions();
