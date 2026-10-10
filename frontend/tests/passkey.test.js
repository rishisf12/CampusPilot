/**
 * Regression tests for the WebAuthn option marshalling.
 *
 * These exist because of a specific shipped bug: `navigator.credentials.create`
 * rejects the whole options object if *any* dictionary member has the wrong
 * type, and the error names that member rather than the cause -
 *
 *   Failed to execute 'create' on 'CredentialsContainer':
 *   Failed to read the 'user' property from 'PublicKeyCredentialCreationOptions':
 *   Failed to read the 'id' property from 'PublicKeyCredentialUserEntity':
 *   The provided value is not of type '(ArrayBuffer or ArrayBufferView)'
 *
 * The server speaks base64url JSON; the WebAuthn API wants `BufferSource`. The
 * server side was covered by tests, and the browser side was only ever checked
 * for *support*, so the conversion itself went untested and broke enrolment for
 * everyone. These pin it down.
 *
 * Run with:  cd frontend && npm test
 */
import assert from 'node:assert/strict';
import { test } from 'vitest';

import { toCreationOptions, toRequestOptions, isPasskeySupported } from '../src/lib/passkey';

//: Shapes a real server response has taken, trimmed of anything irrelevant.
const CREATE_OPTIONS = {
  rp: { name: 'essential - Your Campus Assistant', id: 'localhost' },
  user: {
    id: 'MQ', // base64url for the two bytes "1"
    name: 'rishisf12',
    displayName: '24bme051@iiitdmj.ac.in',
  },
  challenge:
    'pqjeFJyv7fgPCbUBi8WG4nmkw8cDSTDYp7VJE9bj7nRVOxAtcUPE0ZI7ZKt2r_3FhiPPFcmyX8NVbej88-zukQ',
  pubKeyCredParams: [
    { type: 'public-key', alg: -8 },
    { type: 'public-key', alg: -7 },
  ],
  timeout: 60000,
  excludeCredentials: [],
  authenticatorSelection: { residentKey: 'preferred', userVerification: 'required' },
  attestation: 'none',
  _challenge:
    'pqjeFJyv7fgPCbUBi8WG4nmkw8cDSTDYp7VJE9bj7nRVOxAtcUPE0ZI7ZKt2r_3FhiPPFcmyX8NVbej88-zukQ',
  _label: 'Windows Hello',
};

const REQUEST_OPTIONS = {
  challenge:
    'pqjeFJyv7fgPCbUBi8WG4nmkw8cDSTDYp7VJE9bj7nRVOxAtcUPE0ZI7ZKt2r_3FhiPPFcmyX8NVbej88-zukQ',
  rpId: 'localhost',
  timeout: 60000,
  userVerification: 'required',
  allowCredentials: [{ type: 'public-key', id: 'AbN6MTEWv_gsAX8-k7iU5A' }],
  _challenge:
    'pqjeFJyv7fgPCbUBi8WG4nmkw8cDSTDYp7VJE9bj7nRVOxAtcUPE0ZI7ZKt2r_3FhiPPFcmyX8NVbej88-zukQ',
};

/** Every value in the dictionary that WebIDL requires to be a BufferSource. */
function bufferSourceFields(publicKey) {
  const fields = { challenge: publicKey.challenge };
  if (publicKey.user) fields['user.id'] = publicKey.user.id;
  for (const [index, item] of (publicKey.excludeCredentials || []).entries()) {
    fields[`excludeCredentials[${index}].id`] = item.id;
  }
  for (const [index, item] of (publicKey.allowCredentials || []).entries()) {
    fields[`allowCredentials[${index}].id`] = item.id;
  }
  return fields;
}

test('every binary field is a BufferSource, not a string', () => {
  // The actual bug: a string here makes create() throw before it even looks for
  // an authenticator.
  for (const [name, value] of Object.entries(
    bufferSourceFields(toCreationOptions(CREATE_OPTIONS).publicKey)
  )) {
    assert.ok(
      value instanceof Uint8Array || ArrayBuffer.isView(value),
      `${name} must be a BufferSource, got ${typeof value}`
    );
  }
});

test('the reported failure specifically: user.id is bytes', () => {
  const { user } = toCreationOptions(CREATE_OPTIONS).publicKey;
  assert.ok(user.id instanceof Uint8Array);
  assert.notEqual(typeof user.id, 'string');
});

test('sign-in binary fields are bytes too', () => {
  for (const [name, value] of Object.entries(
    bufferSourceFields(toRequestOptions(REQUEST_OPTIONS).publicKey)
  )) {
    assert.ok(
      value instanceof Uint8Array || ArrayBuffer.isView(value),
      `${name} must be a BufferSource, got ${typeof value}`
    );
  }
});

test('base64url decodes to the right bytes', () => {
  const { id } = toCreationOptions(CREATE_OPTIONS).publicKey.user;
  assert.deepEqual([...id], [0x31]); // "MQ" is base64url for "1"
});

test('the full challenge survives the round trip', () => {
  const { challenge } = toCreationOptions(CREATE_OPTIONS).publicKey;
  assert.equal(Buffer.from(challenge).toString('base64url'), CREATE_OPTIONS.challenge);
});

test('credential ids survive the round trip', () => {
  const [{ id }] = toRequestOptions(REQUEST_OPTIONS).publicKey.allowCredentials;
  assert.equal(Buffer.from(id).toString('base64url'), 'AbN6MTEWv_gsAX8-k7iU5A');
});

test('padding-free base64url is handled', () => {
  // "MQ" has no padding; longer values do need it stripped and restored.
  const long = 'AbN6MTEWv_gsAX8-k7iU5A';
  const { id } = toRequestOptions({
    ...REQUEST_OPTIONS,
    allowCredentials: [{ type: 'public-key', id: long }],
  }).publicKey.allowCredentials[0];
  assert.equal(Buffer.from(id).toString('base64url'), long);
});

test('excluded credentials are converted as well', () => {
  const { publicKey } = toCreationOptions({
    ...CREATE_OPTIONS,
    excludeCredentials: [{ type: 'public-key', id: 'AbN6MTEWv_gsAX8-k7iU5A' }],
  });
  assert.ok(publicKey.excludeCredentials[0].id instanceof Uint8Array);
});

test('an empty exclude list is tolerated', () => {
  const { publicKey } = toCreationOptions({
    ...CREATE_OPTIONS,
    excludeCredentials: undefined,
  });
  assert.deepEqual(publicKey.excludeCredentials, []);
});

test('internal bookkeeping fields are not forwarded', () => {
  const { publicKey } = toCreationOptions(CREATE_OPTIONS);
  assert.equal(publicKey._challenge, undefined);
  assert.equal(publicKey._label, undefined);
});

test('server policy is passed through untouched', () => {
  const { publicKey } = toCreationOptions(CREATE_OPTIONS);
  assert.equal(publicKey.rp.id, 'localhost');
  assert.equal(publicKey.authenticatorSelection.userVerification, 'required');
  assert.equal(publicKey.timeout, 60000);
  assert.equal(publicKey.pubKeyCredParams.length, 2);
});

test('the rest of the user entity keeps its string fields', () => {
  const { user } = toCreationOptions(CREATE_OPTIONS).publicKey;
  assert.equal(user.name, 'rishisf12');
  assert.equal(user.displayName, '24bme051@iiitdmj.ac.in');
});

test('support detection is safe to call with no browser globals', () => {
  // Must not throw in a non-browser environment, which is where these run.
  assert.equal(typeof isPasskeySupported(), 'boolean');
});
