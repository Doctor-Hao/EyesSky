<template>
    <h1 class="mb-4">Галерея</h1>

    <!-- Фильтр по категории -->
    <v-card flat outlined class="d-flex align-center mb-3">
      <v-card-title class="pb-6">Категория:</v-card-title>
      <v-card-text class="ma-0 pa-0">
        <v-select
            v-model="selectedCategory"
            :items="uniqueCategories"
            density="compact"
            @change="filterImages"
        />
      </v-card-text>
    </v-card>

    <v-row class="justify-center">
      <v-col cols="12" md="3" lg="2" v-for="image in displayedImages" :key="image.id">
        <v-card :color="'surface'" outlined>
          <v-img
              :src="`data:image/jpeg;base64,${image.image}`"
              height="200px"
              class="white--text"
              :alt="image.title"
          />
           <v-card-text class="">
              <strong>Дата:</strong> {{ new Date(image.date).toLocaleString() }}<br/>
              <strong>Результат предикта:</strong> {{ image.category_type }}
            </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <div id="pagination" class="pagination">
      <button @click="prevPage" :disabled="currentPage === 1">Назад</button>
      <div id="pagination-info">{{ paginationInfo }}</div>
      <button @click="nextPage" :disabled="currentPage >= maxPages">Вперед</button>
    </div>
</template>

<script>
import {ref, computed, onMounted} from 'vue';

export default {
  setup() {
    const socket = new WebSocket(`ws://${window.location.host}/ws/images`);
    const images = ref([]);
    const currentPage = ref(1);
    const imagesPerPage = 12;
    const totalImages = ref(0);
    const selectedCategory = ref('Все'); // Новое состояние для выбранной категории
    const filteredImages = ref([]);

    const paginationInfo = computed(() => {
      return `Страница ${currentPage.value} из ${maxPages.value} (${totalImages.value} изображений всего)`;
    });

    const maxPages = computed(() => {
      return Math.ceil(totalImages.value / imagesPerPage); // Максимальное количество страниц на основе отфильтрованных изображений
    });

    const displayedImages = computed(() => {
      // Возвращаем только изображения для текущей страницы из отфильтрованных
      const start = (currentPage.value - 1) * imagesPerPage;
      return filteredImages.value.slice(start, start + imagesPerPage);
    });

    const uniqueCategories = computed(() => {
      // Получаем уникальные категории из изображений
      const categories = images.value.map(image => image.category_type);
      return ['Все', ...new Set(categories)];
    });

    onMounted(() => {
      socket.addEventListener('open', () => {
        console.log('WebSocket connection established');
        requestImages();  // Запрашиваем весь список изображений
      });

      socket.addEventListener('message', (event) => {
        const response = JSON.parse(event.data);
        console.log('Received data:', response);

        if (response.new_image) {
          addNewImage(response.new_image); // Добавляем новое изображение
        } else {
          updateImageGallery(response.images, response.total); // Обновляем галерею
        }
      });
    });

    function requestImages() {
      // Запрашиваем изображения для текущей страницы
      socket.send(JSON.stringify({action: "get_images", page: currentPage.value, per_page: imagesPerPage}));
    }

    function updateImageGallery(newImages, total) {
      totalImages.value = total;
      images.value = newImages; // Обновляем весь список изображений
      currentPage.value = 1; // Сбрасываем на первую страницу, если загружаем новые изображения
      filterImages(); // Применяем фильтр при обновлении галереи
    }

    function addNewImage(newImage) {
      images.value.unshift(newImage); // Добавляем новое изображение в начало массива
      if (images.value.length > imagesPerPage) {
        images.value.pop(); // Удаляем последнее изображение, если их больше 10
      }
      totalImages.value++; // Увеличиваем общее количество изображений
      filterImages(); // Применяем фильтр при добавлении нового изображения
    }

    function filterImages() {
      if (selectedCategory.value) {
        filteredImages.value = images.value.filter(image => image.category_type === selectedCategory.value);
      } else {
        filteredImages.value = [...images.value]; // Если категория не выбрана, показываем все изображения
      }
      currentPage.value = 1; // Сбрасываем на первую страницу после фильтрации
    }

    function showImageInfo(image) {
      alert(`Image ID: ${image.id}\nPredicted Class: ${image.category_type}`);
    }

    function nextPage() {
      if (currentPage.value < maxPages.value) {
        currentPage.value++;
      }
    }

    function prevPage() {
      if (currentPage.value > 1) {
        currentPage.value--;
      }
    }

    return {
      images,
      displayedImages,
      currentPage,
      paginationInfo,
      nextPage,
      prevPage,
      selectedCategory,
      uniqueCategories,
      filterImages,
    };
  },
};
</script>

<style scoped>
.image-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.image-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.image {
  border: 1px solid #ccc;
  border-radius: 5px;
  cursor: pointer;
  transition: transform 0.2s;
  width: 100px; /* Установите желаемый размер */
  margin: 5px;
}

.image:hover {
  transform: scale(1.05);
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
}

button {
  padding: 10px 15px;
  margin: 0 5px;
  border: none;
  background-color: #007bff;
  color: white;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  background-color: #0056b3;
}

.image-info {
  margin-top: 5px;
  text-align: center;
}
</style>
