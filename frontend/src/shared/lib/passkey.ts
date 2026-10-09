/**
 * Passkey (WebAuthn) helpers for the browser side.
 *
 * Every function here throws a `PasskeyError` with a message worth showing a
 * student. The raw exceptions the WebAuthn API raises - `NotAllowedError`,
 * `InvalidStateError` and friends - are not actionable on their own, and
 * `NotAllowedError` in particular means either "the user pressed cancel" or "the
 * request timed out", so it is translated rather than shown raw.
 */

const API_TIMEOUT_MS = 60000;

export class PasskeyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PasskeyError';
  }
}

/** Is this browser able to use a passkey at all? */
export function isPasskeySupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.PublicKeyCredential !== 'undefined' &&
    typeof navigator.credentials?.create === 'function' &&
    typeof navigator.credentials?.get === 'function'
  );
}

/** base64url -> Uint8Array, which is what WebAuthn reads. */
function fromBase64url(text: string): Uint8Array {
  const padded = text.replace(/-/g, '+').replace(/_/g, '/');
  const paddedOut = padded + '='.repeat((4 - (padded.length % 4)) % 4);
  const binary = atob(paddedOut);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  // Cast to Uint8Array (not Uint8Array<ArrayBufferLike>) to satisfy WebAuthn's BufferSource requirement
  return bytes as Uint8Array;
}

/** Uint8Array -> base64url, which is what the server expects. */
function toBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

interface CreationOptionsFromServer {
  _challenge: string;
  _label: string;
  challenge: string;
  rp: { name: string; id: string };
  user: { id: string; name: string; displayName: string };
  pubKeyCredParams: Array<{ type: string; alg: number }>;
  timeout?: number;
  excludeCredentials?: Array<{ id: string; type: string; transports?: string[] }>;
  authenticatorSelection?: AuthenticatorSelectionCriteria;
  attestation?: AttestationConveyancePreference;
  extensions?: AuthenticationExtensionsClientInputs;
}

interface RequestOptionsFromServer {
  _challenge: string;
  challenge: string;
  rpId: string;
  allowCredentials?: Array<{ id: string; type: string; transports?: string[] }>;
  timeout?: number;
  userVerification?: UserVerificationRequirement;
  extensions?: AuthenticationExtensionsClientInputs;
}

/**
 * The options the server sent, with every binary field decoded and the internal
 * bookkeeping fields removed.
 *
 * The server speaks base64url JSON; the WebAuthn API wants `BufferSource`. So
 * *every* field that carries bytes has to be converted, and missing one fails at
 * the point of use with a message that names the field rather than the cause:
 *
 * - `challenge`                  the server's nonce
 * - `user.id`                    identifies the account to the authenticator
 * - `excludeCredentials[].id`    already-enrolled credentials, to avoid duplicates
 * - `allowCredentials[].id`      (sign-in) which passkeys may be used
 *
 * `authenticatorSelection`, `pubKeyCredParams` and friends are passed through
 * untouched - they are the server's policy, not the client's to second-guess.
 */
export function toCreationOptions(options: CreationOptionsFromServer): {
  publicKey: PublicKeyCredentialCreationOptions;
} {
  const { _challenge, _label, ...rest } = options;
  return {
    publicKey: {
      ...rest,
      challenge: fromBase64url(_challenge) as BufferSource,
      // Required to be bytes. An earlier version of this passed the base64url
      // string through and Chrome rejected it with a message about the user
      // entity's id.
      user: { ...rest.user, id: fromBase64url(rest.user.id) as BufferSource },
      excludeCredentials: (rest.excludeCredentials || []).map(item => ({
        ...item,
        id: fromBase64url(item.id) as BufferSource,
        type: item.type as 'public-key',
        transports: item.transports as AuthenticatorTransport[] | undefined,
      })),
      pubKeyCredParams: rest.pubKeyCredParams.map(p => ({
        ...p,
        type: p.type as 'public-key',
      })),
    },
  };
}

export function toRequestOptions(options: RequestOptionsFromServer): {
  publicKey: PublicKeyCredentialRequestOptions;
} {
  const { _challenge, ...rest } = options;
  return {
    publicKey: {
      ...rest,
      challenge: fromBase64url(_challenge) as BufferSource,
      allowCredentials: (rest.allowCredentials || []).map(
        (item): PublicKeyCredentialDescriptor => ({
          type: item.type as 'public-key',
          id: fromBase64url(item.id) as BufferSource,
          transports: item.transports as AuthenticatorTransport[] | undefined,
        })
      ),
    },
  };
}

/**
 * Turn a WebAuthn DOMException into something a student can act on.
 *
 * `NotAllowedError` covers both a deliberate cancel and the 60-second timeout,
 * so it is reported as a cancel with the timeout mentioned rather than as a
 * failure - otherwise a slow device looks broken.
 */
function explain(error: unknown): PasskeyError {
  const name = (error as { name?: string })?.name || '';
  switch (name) {
    case 'NotAllowedError':
      return new PasskeyError(
        'Passkey prompt was dismissed or timed out. Try again, or use your password.'
      );
    case 'InvalidStateError':
      return new PasskeyError(
        'This device already has a passkey for this account. Sign in with it instead.'
      );
    case 'NotSupportedError':
      return new PasskeyError('This device cannot create a passkey here.');
    case 'SecurityError':
      return new PasskeyError('Passkeys need a secure (https or localhost) connection.');
    case 'AbortError':
      return new PasskeyError('The passkey prompt closed before finishing.');
    default:
      return new PasskeyError(
        (error as Error)?.message || 'The passkey request could not be completed.'
      );
  }
}

/** Wrap a fetch so a stalled request cannot hang the UI indefinitely. */
async function postJson(url: string, body: unknown, token?: string): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body ?? {}),
      signal: controller.signal,
    });

    const text = await response.text();
    let payload: Record<string, unknown> = {};
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { detail: text };
      }
    }

    if (!response.ok) {
      throw new PasskeyError((payload.detail as string) || `Request failed (${response.status}).`);
    }
    return payload;
  } catch (error) {
    if (error instanceof PasskeyError) throw error;
    if ((error as { name?: string })?.name === 'AbortError') {
      throw new PasskeyError('The request timed out. Check your connection and try again.');
    }
    throw new PasskeyError('Could not reach the server. Check your connection and try again.');
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Enrol this device as a passkey.
 *
 * `token` must be a real session: enrolment hands the account a way in without a
 * password, so it is never offered to a signed-out visitor.
 */
/** A credential as the client sees it (matches `passkey_service.describe`). */
export interface DescribedPasskey {
  credential_id: string;
  label: string;
  created_at: string | null;
  last_used_at: string | null;
}

export async function createPasskey({
  token,
  deviceLabel,
}: {
  token: string;
  deviceLabel?: string;
}): Promise<{ message?: string; passkey: DescribedPasskey }> {
  if (!isPasskeySupported()) {
    throw new PasskeyError('This browser does not support passkeys. Try Chrome, Edge or Safari.');
  }

  const options = (await postJson(
    '/auth/passkeys/register/options',
    {},
    token
  )) as CreationOptionsFromServer;
  let credential: PublicKeyCredential | null;
  try {
    credential = (await navigator.credentials.create(
      toCreationOptions(options)
    )) as PublicKeyCredential | null;
  } catch (error) {
    throw explain(error);
  }
  if (!credential) throw new PasskeyError('No passkey was created on this device.');

  const body = {
    credential: {
      id: credential.id,
      rawId: toBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: toBase64url(credential.response.clientDataJSON),
        attestationObject: toBase64url(
          (credential.response as AuthenticatorAttestationResponse).attestationObject
        ),
      },
      clientExtensionResults: credential.getClientExtensionResults?.() || {},
    },
    challenge: options._challenge,
    label: deviceLabel || options._label,
  };
  return postJson('/auth/passkeys/register', body, token) as Promise<{
    message?: string;
    passkey: DescribedPasskey;
  }>;
}

/**
 * Sign in with a passkey.
 *
 * With a `username` the device is offered only that account's passkeys, which is
 * predictable. With none, the authenticator offers whatever passkeys it holds -
 * that option needs a *discoverable* credential, so it silently fails on
 * devices that were enrolled before this was supported.
 */
export async function authenticateWithPasskey({ username }: { username?: string } = {}): Promise<{
  access_token: string;
}> {
  if (!isPasskeySupported()) {
    throw new PasskeyError('This browser does not support passkeys. Try Chrome, Edge or Safari.');
  }

  const options = (await postJson('/auth/passkeys/login/options', {
    username: username ? username.trim() : null,
  })) as RequestOptionsFromServer;
  let credential: PublicKeyCredential | null;
  try {
    credential = (await navigator.credentials.get(
      toRequestOptions(options)
    )) as PublicKeyCredential | null;
  } catch (error) {
    throw explain(error);
  }
  if (!credential) throw new PasskeyError('No passkey was used on this device.');

  const body = {
    credential: {
      id: credential.id,
      rawId: toBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: toBase64url(credential.response.clientDataJSON),
        authenticatorData: toBase64url(
          (credential.response as AuthenticatorAssertionResponse).authenticatorData
        ),
        signature: toBase64url((credential.response as AuthenticatorAssertionResponse).signature),
        userHandle: (credential.response as AuthenticatorAssertionResponse).userHandle
          ? toBase64url((credential.response as AuthenticatorAssertionResponse).userHandle!)
          : null,
      },
      clientExtensionResults: credential.getClientExtensionResults?.() || {},
    },
    challenge: options._challenge,
  };

  // No token: this request is how a session is obtained.
  return postJson('/auth/passkeys/login', body) as Promise<{ access_token: string }>;
}
