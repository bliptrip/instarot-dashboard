import { useState, useEffect } from "react";

export default function useLiveData() {
  const [readings, setReadings] = useState({});

  useEffect(() => {
    const source = new EventSource("/stream");
    source.onmessage = (e) => {
      const { type, device, data } = JSON.parse(e.data);
      if (type === "reading") {
        setReadings(prev => ({ ...prev, [device]: data }));
      }
    };
    return () => source.close();
  }, []);

  return readings;
}