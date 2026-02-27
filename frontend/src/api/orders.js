// src/api/orders.js
import apiClient from './apiClient';

export async function getOrders() {
  const response = await apiClient.get('/orders');
  return response.data;
}