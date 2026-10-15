#!/usr/bin/env node
/**
 * Scaffold a new frontend admin feature module
 * Usage: node scaffold-feature.js <feature-name>
 */

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Usage: node scaffold-feature.js <feature-name>');
  process.exit(1);
}

const featureName = args[0];
const featureDir = featureName.toLowerCase().replace(/-/g, '_');
const featureTitle = featureName
  .split('_')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join(' ');
const modelName = featureName
  .split('_')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join('');
const featureTitle = featureName
  .split('_')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join(' ');

const basePath = path.join(
  __dirname,
  '..',
  'src',
  'modules',
  'admin',
  'features',
  'admin',
  featureDir
);
const featureFile = path.join(basePath, `${modelName}.tsx`);

const imports = `import { useEffect, useState } from 'react';
import { ${modelName === 'User360' ? 'User' : ''} } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Input, Button, Tabs, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';
`;

const template = `import { useEffect, useState } from 'react';
import { ${modelName === 'User360' ? 'User' : ''} } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Input, Button, Tabs, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function ${modelName}({ onError }: { onError?: (m: string) => void }) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.${featureDir}();
      setData(data.${featureDir} || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      onError?.(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>Loading…</Card>;

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      <Card>
        <h3 className="text-lg font-semibold mb-4">${featureTitle}</h3>
        <p className="text-sm text-gray-500 mb-4">Feature implementation pending.</p>
      </Card>
    </div>
  );
}
`;

const featureDir = process.argv[2]?.toLowerCase().replace(/-/g, '_');
if (!featureDir) {
  console.error('Usage: node scaffold-feature.js <feature-name>');
  process.exit(1);
}

const modelName = featureDir
  .split('_')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join('');
const featureTitle = featureDir
  .split('_')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join(' ');
const basePath = path.join(
  __dirname,
  '..',
  'src',
  'modules',
  'admin',
  'features',
  'admin',
  featureDir
);
const featureFile = path.join(basePath, `${featureDir}.tsx`);

if (fs.existsSync(basePath)) {
  console.error(`Directory ${basePath} already exists.`);
  process.exit(1);
}

fs.mkdirSync(basePath, { recursive: true });

const content = `import { useEffect, useState } from 'react';
import { adminApi } from '@/api';
import { Card } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function ${featureDir.charAt(0).toUpperCase() + featureDir.slice(1)}({ onError }: { onError?: (m: string) => void }) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.${featureDir}();
      setData(data.${featureDir} || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>Loading…</div>;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">${featureDir.charAt(0).toUpperCase() + featureDir.slice(1)}</h2>
      <div className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Feature implementation pending.
      </div>
    </div>
  );
}
`;

const filePath = path.join(basePath, `${featureDir}.tsx`);
fs.writeFileSync(filePath, content);
console.log(`Created ${filePath}`);

console.log('\n✅ Feature scaffolded successfully!');
console.log(`📁 Location: ${basePath}`);
console.log('\n🔧 Next steps:');
console.log('  1. Implement the adminApi methods in api.ts');
console.log('  2. Add backend routes in Python');
console.log('  3. Add to AdminPanel.tsx tabs');
console.log('  4. Run backend alembic migrations');
