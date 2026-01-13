import 'package:flutter/material.dart';

/// Product list screen with null safety issue for task_008
class ProductListScreen extends StatelessWidget {
  final List<Product?> products;
  
  const ProductListScreen({super.key, required this.products});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Products')),
      body: ListView.builder(
        itemCount: products.length,
        itemBuilder: (context, index) {
          final product = products[index];
          // task_008: Fix null pointer exception here
          // product can be null but we access product.name directly
          return ListTile(
            title: Text(product.name), // BUG: product might be null!
            subtitle: Text('\$${product.price}'),
          );
        },
      ),
    );
  }
}

class Product {
  final String name;
  final double price;
  
  Product({required this.name, required this.price});
}
