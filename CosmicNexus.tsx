import React, { useState } from 'react';

const CosmicNexus = ({ stats }) => {
  // Example use of useState (lines 35-36 as mentioned)
  const [count, setCount] = useState(0);

  // Accessing the correct property (stats.sentimentCounts instead of stats.sentimentDistribution)
  const sentimentData = stats.sentimentCounts || [];

  return (
    <div>
      <h1>Cosmic Nexus</h1>
      <div>Sentiment Counts: {JSON.stringify(sentimentData)}</div>
    </div>
  );
};

export default CosmicNexus;
