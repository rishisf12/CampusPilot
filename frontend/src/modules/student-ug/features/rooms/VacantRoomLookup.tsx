/**
 * Vacant room lookup lives in the shared layer so faculty can use the same
 * component; this re-export keeps the student module's import path stable.
 */
export { default } from '@shared/features/rooms/VacantRoomLookup';
