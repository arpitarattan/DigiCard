import React, { useEffect } from 'react';
import './GyroParallax.css';

export default function GyroParallax({ layers, original }) {
    console.log(layers)
  useEffect(() => {
    const handleMotion = (event) => {
      const x = event.gamma || 0;
      const y = event.beta || 0;

      document.querySelectorAll('.layer').forEach((layer, i) => {
        const depth = (i + 1) * 5;
        layer.style.transform = `translate(${x * depth}px, ${y * depth}px)`;
      });
    };

    if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission === 'function') {
      document.getElementById("motion-btn").onclick = () => {
        DeviceOrientationEvent.requestPermission()
          .then(permissionState => {
            if (permissionState === "granted") {
              window.addEventListener("deviceorientation", handleMotion);
            }
          })
          .catch(console.error);
      };
    } else {
      window.addEventListener("deviceorientation", handleMotion);
    }

    return () => window.removeEventListener("deviceorientation", handleMotion);
  }, []);

  return (
    <div className="parallax-container">
      <img src={original} className="bg-layer" alt="Original" />
      {layers.map((layer, i) => (
        <img key={i} src={layer.image_url} className="layer" style={{ zIndex: i }} alt={`Layer ${i}`} />
      ))}
      <button id="motion-btn" className="motion-button">Enable Motion</button>
    </div>
  );
}
