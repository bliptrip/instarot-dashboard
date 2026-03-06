import { useState, useEffect } from "react";

const MAX_POINTS = 4096;

export default function useLivePIDs(device) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!device) return;
    setHistory([]);

    const source = new EventSource(`/stream-pids/${device}`);
    source.onmessage = (e) => {
      const point = JSON.parse(e.data);
      const time = new Date(point.ts * 1000).toLocaleTimeString();
      setHistory(prev => {
        const next = [...prev, { ...point, time }];
        return next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next;
      });
    };

    return () => source.close();
  }, [device]);

  return history;
}
