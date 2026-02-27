// src/api/wishlist.js
import apiClient from './apiClient';

export async function getWishlist() {
  const response = await apiClient.get('/wishlist');
  return response.data;
}

export async function addToWishlist(product) {
  const response = await apiClient.post('/wishlist', {
    product_id:     Number(product.id),
    product_name:   product.name,
    product_source: product.source || 'static',
    store_name:     product.store,
  });
  return response.data;
}

export async function removeFromWishlist(productId) {
  const response = await apiClient.delete(`/wishlist/${Number(productId)}`);
  return response.data;
}