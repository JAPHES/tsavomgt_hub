(() => {
    const pad = value => String(value).padStart(2, "0");
    const updateElapsed = () => {
        document.querySelectorAll("[data-elapsed]").forEach(node => {
            const started = Date.parse(node.dataset.checkIn);
            if (Number.isNaN(started)) return;
            const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const remaining = seconds % 60;
            node.textContent = `${hours}h ${pad(minutes)}m ${pad(remaining)}s`;
        });
        const clock = document.getElementById("local-clock");
        if (clock) clock.textContent = new Intl.DateTimeFormat("en-KE", {timeZone: "Africa/Nairobi", hour: "2-digit", minute: "2-digit", second: "2-digit"}).format(new Date());
    };
    updateElapsed();
    window.setInterval(updateElapsed, 1000);
})();
