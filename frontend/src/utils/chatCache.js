// frontend/src/utils/chatCache.js

const messageCache = new Map();

/**
 * Load messages for a given user ID from memory cache or localStorage.
 * @param {number|string} userId
 * @returns {Array} messages
 */
export function loadMessages(userId) {
  if (!userId) {
    console.log('chatCache: loadMessages called with no userId');
    return [];
  }
  const key = `chatMessages_${userId}`;
  console.log(`chatCache: loading messages for key ${key}`);
  if (messageCache.has(key)) {
    console.log('chatCache: found in memory cache');
    return messageCache.get(key);
  }
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    console.log(`chatCache: loaded from localStorage, length=${parsed.length}`);
    messageCache.set(key, parsed);
    return parsed;
  } catch {
    console.log('chatCache: error loading from localStorage');
    return [];
  }
}

/**
 * Save messages for a given user ID to memory cache and localStorage.
 * @param {number|string} userId
 * @param {Array} messages
 */
export function saveMessages(userId, messages) {
  if (!userId) {
    console.log('chatCache: saveMessages called with no userId, skipping');
    return;
  }
  const key = `chatMessages_${userId}`;
  console.log(`chatCache: saving messages for key ${key}, length=${messages.length}`);
  messageCache.set(key, messages);
  try {
    localStorage.setItem(key, JSON.stringify(messages));
    console.log('chatCache: saved to localStorage');
  } catch {
    console.log('chatCache: error saving to localStorage');
  }
}

/**
 * Clear all messages for a given user ID from memory cache and localStorage.
 * @param {number|string} userId
 */
export function clearMessages(userId) {
  if (!userId) {
    console.log('chatCache: clearMessages called with no userId');
    return;
  }
  const key = `chatMessages_${userId}`;
  console.log(`chatCache: clearing messages for key ${key}`);
  messageCache.delete(key);
  try {
    localStorage.removeItem(key);
    console.log('chatCache: removed from localStorage');
  } catch {
    console.log('chatCache: error removing from localStorage');
  }
}