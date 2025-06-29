import React, { useState } from 'react';
import { uploadImage } from './api';
import GyroParallax from './GyroParallax';

function App() {
  const [layers, setLayers] = useState([]);
  const [original, setOriginal] = useState("");

  async function handleUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const result = await uploadImage(file);
    setOriginal(result.original);
    setLayers(result.layers);
  }

  return (
    <div>
      <input type="file" onChange={handleUpload} />
      {layers.length > 0 && <GyroParallax layers={layers} original={original} />}
    </div>
  );
}

export default App;
